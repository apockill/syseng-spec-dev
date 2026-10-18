"""Builds small specs on disk for tests."""

import os
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
        tests = self.root.parent / "tests" / "test_core.py"  # the tests the base spec links to (CHECK-4)
        if not tests.exists():
            tests.parent.mkdir(parents=True, exist_ok=True)
            tests.write_text("def test_stamp():\n    pass\n\n\ndef test_other():\n    pass\n")
        for rel, data in self.files.items():
            yamlio.write(self.root / rel, data)
        if render_views:
            render.write_views(model.load(self.root))
        return self.root

    def load(self) -> model.Spec:
        return model.load(self.root)

    def findings(self) -> list[check.Finding]:
        return check.check(self.load())

    def codes(self, severity: str = "error") -> list[str]:
        return [f.code for f in self.findings() if f.severity == severity]


@pytest.fixture
def spec(tmp_path) -> SpecBuilder:
    return SpecBuilder(tmp_path / "spec")


@pytest.fixture(autouse=True)
def _own_home(tmp_path, monkeypatch):
    """Every test gets a home folder of its own, so `spec init`'s user-level links never touch the real one."""
    (tmp_path / "home").mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)


@pytest.fixture
def machine(tmp_path, monkeypatch) -> Path:
    """A machine with the toolkit installed: `spec` on the PATH, running this checkout."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "spec"
    src = Path(__file__).resolve().parents[1] / "src"
    shim.write_text(f'#!/bin/sh\nPYTHONPATH="{src}" exec "{sys.executable}" -m syseng "$@"\n')
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return bin_dir
