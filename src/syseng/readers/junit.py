"""JUnit XML, the export most test tools share. A test's identifier is `classname.name`, or `name` alone."""

import xml.etree.ElementTree as ET

from syseng import readers


_NOT_RUN = {"notrun", "skipped"}  # GoogleTest marks a test it didn't run with an attribute, not a child element


def _tag(element) -> str:
    return element.tag.rpartition("}")[2]  # some tools add an XML namespace


def cases(path):
    """Each test case in a report: its classname, name and outcome."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise readers.ReaderError(f"{path} isn't valid XML: {e}") from e
    for case in (e for e in tree.getroot().iter() if _tag(e) == "testcase"):
        kinds = {_tag(child) for child in case}
        skipped = "skipped" in kinds or case.get("status") in _NOT_RUN or case.get("result") == "skipped"
        outcome = readers.FAIL if kinds & {"failure", "error"} else readers.SKIP if skipped else readers.PASS
        yield case.get("classname") or "", case.get("name") or "", outcome


def read(path, root):
    tests = {}
    for classname, name, outcome in cases(path):
        readers.merge(tests, f"{classname}.{name}" if classname else name, outcome)
    return tests
