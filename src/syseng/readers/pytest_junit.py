"""pytest's JUnit XML. A test's identifier is its pytest node ID without parameters, as `path::Class::test`."""

import re

from syseng import readers
from syseng.readers import junit


def _node(classname, name, root):
    if not classname and (root / name.replace(".", "/")).with_suffix(".py").exists():
        return name.replace(".", "/") + ".py"  # a file that failed to import: pytest reports the module, no test
    parts = classname.split(".")
    for n in range(len(parts), 0, -1):  # the file ends where the dotted name stops being a path
        if (root / "/".join(parts[:n])).with_suffix(".py").exists():
            return "::".join(["/".join(parts[:n]) + ".py", *parts[n:], name])
    return f"{classname}.{name}" if classname else name


def read(path, root):
    tests = {}
    for classname, name, outcome in junit.cases(path):
        readers.merge(tests, _node(classname, re.sub(r"\[.*\]$", "", name), root), outcome)
    return tests
