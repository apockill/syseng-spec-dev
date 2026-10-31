"""Test results from a project's pipeline, and each verification item's status from them (SYS-57).

The toolkit runs no tests. Each pipeline step hands over its report with `spec results add`, in any order, and
`spec results status` combines what's there. One file per implementation, revision and step, in a folder version
control ignores, so a retry replaces its step and a later step adds to the rest (VERIFY-18).
"""

import datetime
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import quote

from syseng import levels, readers, vcs
from syseng.model import Spec

PASSING, FAILING, NOT_RUN, NOT_IMPLEMENTED = "passing", "failing", "not yet run", "not implemented"
STATUSES = (PASSING, FAILING, NOT_RUN, NOT_IMPLEMENTED)
_NO_TESTS = {"reasoning check", "manual"}  # judged, not run: a verdict is a result named by the item's ID (VERIFY-29)


def directory(spec: Spec) -> Path:
    return spec.results_dir or spec.repo_root() / ".syseng" / "results"


def implementations(spec: Spec) -> list[dict]:
    return [i for i in spec.config.get("implementations") or [] if isinstance(i, dict)]


def primary(spec: Spec) -> str:
    named = implementations(spec)
    return next((i["name"] for i in named if i.get("primary")), named[0]["name"] if named else "")


def _path(spec: Spec, implementation: str, revision: str, step: str) -> Path:
    return directory(spec) / quote(implementation, safe="") / quote(revision, safe="") / f"{quote(step, safe='')}.json"


def _moment(when: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(when).astimezone()


def record(spec: Spec, implementation: str, step: str, revision: str, tests: dict[str, str], when: str | None = None,
           add: bool = False) -> Path:
    """VERIFY-17, VERIFY-18: one step's results for one revision. A report replaces the step's earlier results; with
    `add`, outcomes given one at a time join them, so several verdicts can share a step."""
    path = _path(spec, implementation, revision, step)
    path.parent.mkdir(parents=True, exist_ok=True)
    if add and path.exists():
        tests = {**json.loads(path.read_text()).get("tests", {}), **tests}
    when = when or datetime.datetime.now().astimezone().isoformat(timespec="microseconds")
    path.write_text(json.dumps({"implementation": implementation, "step": step, "revision": revision, "when": when,
                                "tests": tests}, indent=1))
    if spec.results_dir is None:
        vcs.backend(spec.repo_root()).ignore(directory(spec))
    return path


def _records(spec: Spec, implementation: str) -> list[dict]:
    out = []
    for path in (directory(spec) / quote(implementation, safe="")).glob("*/*.json"):
        try:
            one = json.loads(path.read_text())
            _moment(one["when"]), one["tests"].items(), one["revision"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            print(f"spec results: skipping {path}, which can't be read", file=sys.stderr)
            continue
        out.append(one)
    return sorted(out, key=lambda r: _moment(r["when"]))


def latest(spec: Spec, implementation: str) -> dict[str, dict]:
    """VERIFY-20: each test's newest result. A skip isn't a result: the test wasn't run."""
    out = {}
    for r in _records(spec, implementation):
        for name, outcome in r["tests"].items():
            if outcome != readers.SKIP:
                out[name] = {"outcome": outcome, "revision": r["revision"], "when": r["when"]}
    return out


def _bare(name: str) -> str:
    return re.sub(r"\[.*\]$", "", name)


class _Index:
    """Finds what a link names: the identifier itself, any of its parametrized cases, every test in a linked file,
    and, for a GoogleTest link `file::Suite.Test`, the `Suite.Test` that JUnit XML reports."""

    def __init__(self, names):
        self.exact, self.bare, self.file = set(names), {}, {}
        for name in self.exact:
            self.bare.setdefault(_bare(name), []).append(name)
            if "::" in name:
                self.file.setdefault(name.partition("::")[0], []).append(name)

    def names(self, link: str) -> list[str]:
        found = {link} & self.exact
        bare = _bare(link)
        file, _, test = bare.partition("::")
        found.update(self.bare.get(bare, []))
        if not test:
            found.update(self.file.get(link, []))
        elif "." in test:
            found.update(self.bare.get(test, []))
        return sorted(found)


def _results_for(link: str, found: dict, index: _Index) -> list[dict]:
    results = [found[n] for n in index.names(link)]
    broken = found.get(link.partition("::")[0])  # the whole file failed, as when it can't be imported
    if "::" in link and broken and broken["outcome"] == readers.FAIL and all(
            _moment(broken["when"]) >= _moment(r["when"]) for r in results):
        return [broken]
    return results


@dataclass
class Row:
    id: str
    status: str
    verifies: list[str]
    level: str                     # the highest level of intent among the requirements it verifies
    locked: bool
    last_tested: str = ""          # the revision of its newest result (VERIFY-21)
    failed: list[str] = field(default_factory=list)
    when: str = ""


def _rollup(spec: Spec, vi, implementation: str, found: dict, index: _Index, done: dict) -> tuple:
    """A roll-up is as good as what verifies the requirements under it, and a child with nothing verifying it counts
    as not run. It takes no verdict of its own: its children decide."""
    done[vi.id] = (NOT_RUN, "", [], "")  # a roll-up that reaches itself adds nothing
    seen = []
    for r in vi.data.get("verifies") or []:
        for child in spec.requirements():
            if child.data.get("traces_to") != r:
                continue
            below = [v for v in spec.of_kind("vi") if child.id in (v.data.get("verifies") or []) and v.id != vi.id]
            seen += [_status(spec, v, implementation, found, index, done) for v in below] or [(NOT_RUN, "", [], "")]
    words = {s[0] for s in seen}
    status = (FAILING if FAILING in words else NOT_RUN if NOT_RUN in words or not seen
              else NOT_IMPLEMENTED if NOT_IMPLEMENTED in words else PASSING)
    tested = max((s for s in seen if s[3]), key=lambda s: _moment(s[3]), default=(NOT_RUN, "", [], ""))
    return status, tested[1], [], tested[3]


def _status(spec: Spec, vi, implementation: str, found: dict, index: _Index, done: dict) -> tuple:
    if vi.id in done:
        return done[vi.id]
    data = vi.data
    if data.get("technique") == "roll-up":
        done[vi.id] = _rollup(spec, vi, implementation, found, index, done)
        return done[vi.id]
    links = [str(x) for x in ((data.get("tests") or {}).get(implementation) or [])]
    verdict = found.get(vi.id)
    if not links and not verdict:
        done[vi.id] = (NOT_RUN if data.get("technique") in _NO_TESTS else NOT_IMPLEMENTED, "", [], "")
        return done[vi.id]
    results = {link: _results_for(link, found, index) for link in links}
    if verdict:
        results[vi.id] = [verdict]
    every = [r for rs in results.values() for r in rs]
    failed = [k for k, rs in results.items() if any(r["outcome"] == readers.FAIL for r in rs)]
    newest = max(every, key=lambda r: _moment(r["when"])) if every else {"revision": "", "when": ""}
    status = FAILING if failed else PASSING if all(results.values()) else NOT_RUN
    done[vi.id] = (status, newest["revision"], failed, newest["when"])
    return done[vi.id]


def rows(spec: Spec, implementation: str) -> list[Row]:
    """Each verification item's status in an implementation (VERIFY-5)."""
    found, done, out = latest(spec, implementation), {}, []
    index = _Index(found)
    for vi in spec.of_kind("vi"):
        status, tested, failed, when = _status(spec, vi, implementation, found, index, done)
        verifies = list(vi.data.get("verifies") or [])
        lv = [levels.level_of(spec, r).level for r in verifies if r in spec.items]
        best = min(lv, key=levels.ORDER.index) if lv else levels.ADDED
        out.append(Row(vi.id, status, verifies, best, levels.EXPLICIT in lv, tested, failed, when))
    return out


def unlinked(spec: Spec, implementation: str) -> list[str]:
    """VERIFY-24: tests in the results, even skipped ones, that no verification item links."""
    every = {name for r in _records(spec, implementation) for name in r["tests"]}
    index = _Index(every)
    linked = {vi.id for vi in spec.of_kind("vi")}
    for vi in spec.of_kind("vi"):
        for link in (vi.data.get("tests") or {}).get(implementation) or []:
            linked.update(index.names(str(link)))
            linked.add(str(link).partition("::")[0])
    return sorted(every - linked)


def report(spec: Spec) -> dict:
    """Everything `spec results status` and the review page show."""
    out = {}
    for i in implementations(spec):
        name = i["name"]
        items = rows(spec, name)
        out[name] = {"primary": bool(i.get("primary")),
                     "counts": {s: sum(1 for r in items if r.status == s) for s in STATUSES},
                     "failing": sorted((asdict(r) for r in items if r.status == FAILING),
                                       key=lambda r: levels.ORDER.index(r["level"])),
                     "not_run_locked": [asdict(r) for r in items if r.status == NOT_RUN and r.locked],
                     "items": [asdict(r) for r in items],
                     "unlinked": unlinked(spec, name)}
    return out
