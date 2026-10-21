"""The Markdown views are gone: the review page replaced them (SYS-45, DR-60, DR-65).

What's left here removes the views earlier versions generated, so a repository reflects the current
system, and a helper for ordering IDs.
"""

from pathlib import Path

from syseng import changes
from syseng.model import Spec

RETIRED_VIEWS = ("requirements.md", "decisions.md")


def views(spec: Spec) -> dict[str, str]:
    """No Markdown views are generated any more; `spec review` writes the review page instead."""
    return {}


def stale_views(spec: Spec) -> list[Path]:
    """Markdown views earlier versions generated: the requirements and decisions views, and one per change record."""
    out = [spec.root / name for name in RETIRED_VIEWS if (spec.root / name).exists()]
    out += [c.path.with_suffix(".md") for c in changes.all_changes(spec) if c.path.with_suffix(".md").exists()]
    return out


def stale_change_views(spec: Spec) -> list[Path]:
    return [p for p in stale_views(spec) if p.parent.name == "changes"]


def write_views(spec: Spec) -> list[Path]:
    """Removes the views earlier versions generated. Returns what it removed."""
    removed = stale_views(spec)
    for path in removed:
        path.unlink()
    return removed


def _id_key(s: str):
    head, _, num = s.rpartition("-")
    digits = num.lstrip("V")
    return (head, int(digits) if digits.isdigit() else 0)
