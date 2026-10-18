"""Each test a verification item links to exists, as a file and a test name in it (CHECK-4)."""

import pytest

from syseng import testlinks

PY = '''
import pytest

def test_stamp():
    pass

class TestWidget:
    async def test_shine(self):
        pass
'''

CPP = '''
#include <gtest/gtest.h>

TEST(WidgetTest, Stamps) {}
TEST_F(WidgetFixture, Shines) {}
TEST_P(WidgetParams, Counts) {}
'''


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_core.py").write_text(PY)
    (tmp_path / "tests/core_test.cpp").write_text(CPP)
    (tmp_path / "bench.sh").write_text("run_widget_bench\n")
    return tmp_path


@pytest.mark.parametrize("link", [
    "tests/test_core.py",
    "tests/test_core.py::test_stamp",
    "tests/test_core.py::test_stamp[ink]",
    "tests/test_core.py::TestWidget::test_shine",
    "tests/core_test.cpp::WidgetTest.Stamps",
    "tests/core_test.cpp::WidgetFixture.Shines",
    "tests/core_test.cpp::WidgetParams.Counts",
    "bench.sh::run_widget_bench",
])
def test_links_to_existing_tests_pass(repo, link):
    assert testlinks.missing(repo, link) is None


@pytest.mark.parametrize("link, problem", [
    ("tests/test_gone.py::test_stamp", "there's no file tests/test_gone.py"),
    ("tests/test_core.py::test_polish", "has no test test_polish"),
    ("tests/test_core.py::TestGadget::test_shine", "has no class TestGadget"),
    ("tests/core_test.cpp::WidgetTest.Polishes", "has no GoogleTest WidgetTest.Polishes"),
    ("tests/core_test.cpp::Stamps", "isn't a GoogleTest name"),
    ("bench.sh::run_gadget_bench", "doesn't mention run_gadget_bench"),
])
def test_links_to_missing_tests_say_what_is_missing(repo, link, problem):
    assert problem in testlinks.missing(repo, link)


def test_the_checker_reports_broken_links_and_unknown_implementations(spec):
    vi = spec.files["elements/CORE/verification.yaml"][0]
    vi["tests"] = {"python": ["tests/test_core.py::test_polish", "tests/test_gone.py"], "rust": ["src/lib.rs"]}
    spec.write()
    messages = [f.message for f in spec.findings() if f.code == "V002"]
    assert any("has no test test_polish" in m for m in messages)
    assert any("there's no file tests/test_gone.py" in m for m in messages)
    assert any("'rust'" in m for m in messages)
    vi["tests"] = {"python": ["tests/test_core.py::test_stamp"]}
    spec.write()
    assert "V002" not in spec.codes()


def test_edits_check_links_against_the_real_repository(spec):
    from syseng import changes, edit
    root = spec.write()
    changes.start(spec.load(), "widgets", None, None, None)
    relink = {"edits": [{"modify": "CORE-V1", "set": {"tests": {"python": ["tests/test_core.py::test_other"]}},
                         "reason": "renamed"}]}
    assert edit.run(root, relink).applied                         # the scratch copy finds the real tests
    broken = {"edits": [{"modify": "CORE-V1", "set": {"tests": {"python": ["tests/test_core.py::test_typo"]}},
                         "reason": "typo"}]}
    result = edit.run(root, broken)
    assert not result.applied and [f.code for f in result.errors] == ["V002"]
