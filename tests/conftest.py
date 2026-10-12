"""Builds small specs on disk for tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syseng import check, model, render, yamlio  # noqa: E402


def _base() -> dict:
    return {
        "toolkit.yaml": {"spec_version": 1, "element_order": ["SYS", "CORE"],
                         "implementations": [{"name": "python", "language": "python", "root": ".", "primary": True}]},
        "elements/SYS/element.yaml": {"id": "SYS", "title": "The system", "parent": None, "depends_on": [],
                                      "purpose": "The whole product."},
        "elements/SYS/needs.yaml": [{"id": "NEED-1", "text": "The engineer needs widgets.", "origin": "engineer",
                                     "source": '"widgets please"', "context": "they like widgets."}],
        "elements/SYS/requirements.yaml": [{"id": "SYS-1", "kind": "system", "text": "The system shall make widgets.",
                                            "origin": "engineer", "serves": ["NEED-1"], "source": '"widgets please"'}],
        "elements/CORE/element.yaml": {"id": "CORE", "title": "Core", "parent": "SYS", "depends_on": [],
                                       "purpose": "Makes the widgets."},
        "elements/CORE/requirements.yaml": [{"id": "CORE-1", "text": "The core shall stamp each widget.",
                                             "origin": "agent", "traces_to": "SYS-1", "why": "stamped widgets sell."}],
        "elements/CORE/verification.yaml": [{"id": "CORE-V1", "verifies": ["CORE-1"], "method": "test",
                                             "technique": "unit test", "origin": "agent",
                                             "description": "A made widget carries a stamp.",
                                             "tests": {"python": ["tests/test_core.py::test_stamp"]}}],
        "approvals.yaml": [],
        "retired.yaml": [],
        "questions.yaml": [],
    }


class SpecBuilder:
    """A writable spec in a temporary directory. Edit `files`, then call `write()`."""

    def __init__(self, root: Path):
        self.root = root
        self.files = _base()

    def write(self, render_views: bool = True) -> Path:
        for rel, data in self.files.items():
            yamlio.write(self.root / rel, data)
        if render_views:
            render.write_views(model.load(self.root))
        return self.root

    def load(self) -> model.Spec:
        return model.load(self.root)

    def findings(self, merge: bool = False) -> list[check.Finding]:
        return check.check(self.load(), merge=merge)

    def codes(self, merge: bool = False, severity: str = "error") -> list[str]:
        return [f.code for f in self.findings(merge) if f.severity == severity]


@pytest.fixture
def spec(tmp_path) -> SpecBuilder:
    return SpecBuilder(tmp_path / "spec")
