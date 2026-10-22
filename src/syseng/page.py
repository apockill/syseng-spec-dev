"""Generates the review page: one self-contained HTML file (SYS-45, REVIEW-22, DR-60).

The page embeds the data `pagedata.build` returns and the script that renders it. It loads nothing
from the network, so it works offline, from a plain file, and for a private spec.
"""

import json
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"


def render(data: dict) -> str:
    template = (WEB / "review.html").read_text()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    payload = payload.replace("</", "<\\/")  # nothing in the data can close the script element
    return (template.replace("/*CSS*/", (WEB / "review.css").read_text())
            .replace("/*JS*/", (WEB / "review.js").read_text())
            .replace("/*DATA*/", payload))


def default_path(spec_root: Path) -> Path:
    """Beside the toolkit's hook, outside the spec, and ignored by version control."""
    return spec_root.parent / ".syseng" / "review.html"


def write(data: dict, out: Path, snapshots: Path) -> Path:
    """Writes the page, and keeps what it showed locally so a later comparison knows exactly what was seen (DR-59)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data))
    snapshots.mkdir(parents=True, exist_ok=True)
    (snapshots / f"{data['meta']['review']}.json").write_text(json.dumps(data, ensure_ascii=False, default=str))
    for old in sorted(snapshots.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-20]:
        old.unlink()
    ignore = out.parent / ".gitignore"
    wanted = [out.name, snapshots.name + "/"]
    have = ignore.read_text().splitlines() if ignore.exists() else []
    if any(w not in have for w in wanted):
        ignore.write_text("\n".join(dict.fromkeys(have + wanted)) + "\n")
    return out
