"""Problem reports: an agent's account of a problem with the toolkit, sent as an issue with consent (SYS-56).

The toolkit's repository is public, so a report says what happened and leaves the project out. It says nothing of
how to fix the problem, so whoever reads it starts from the real problem and not from one agent's idea of a fix.
"""

import hashlib
import re
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REPOSITORY = "apockill/syseng-spec-dev"
TITLE_PREFIX = "[agent report] "
SECTIONS = ("The task", "How the agent went about it", "The problem", "How the agent got past it")
TEMPLATE = """\
## The task
<!-- What the agent was asked to do and why, in general terms. Say what kind of project it was, not which one. -->

## How the agent went about it
<!-- The steps and commands it used, in order, up to the problem. -->

## The problem
<!-- What it expected or needed, what happened instead, and the toolkit's exact message if there was one. A missing feature or a papercut counts. -->

## How the agent got past it
<!-- The workaround, or "It didn't." -->
"""
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)[ \t]*$", re.M)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_ABSOLUTE_PATH = re.compile(r"(?<![\w.~/-])(?:~/|/[\w.-]+/[\w.-]|[A-Za-z]:\\|file:/)")


def _clean(text: str) -> str:
    return _COMMENT.sub("", text.replace("\r\n", "\n"))


def problems(text: str) -> list[str]:
    """What's wrong with a report's shape: an empty section, or anything the template doesn't have (CLI-31)."""
    clean = _clean(text)
    parts = _HEADING.split(clean)
    named = list(zip(parts[1::2], parts[2::2]))
    names = [h.group(0).strip() for h in _HEADING.finditer(clean)]
    out = [f"the section `{n}` isn't in the template; a report describes the problem and proposes no solution"
           for n in names if n.removeprefix("## ") not in SECTIONS or not n.startswith("## ")]
    out += [f"the section `{n}` appears twice" for n in SECTIONS if [k for k, _ in named].count(n) > 1]
    out += [f"the section `{n}` is empty" for n in SECTIONS if not any(k == n and v.strip() for k, v in named)]
    if parts[0].strip():
        out.append("there is text before the first section")
    return out


def _repository_name(remote: str) -> str:
    """owner/name from any form of remote address, or the last folder of a local one."""
    return "/".join(re.split(r"[/:]", remote.strip().rstrip("/").removesuffix(".git"))[-2:]).strip("/")


def leaks(text: str, author: str, remote: str) -> list[str]:
    """What in a report would identify the project or the person (CLI-32). A backstop: it can't catch everything."""
    out = [f"email address {m}" for m in sorted(set(_EMAIL.findall(text)))]
    out += [f"absolute path on line {n}" for n, line in enumerate(text.splitlines(), 1) if _ABSOLUTE_PATH.search(line)]
    for name in author.split("<")[0].split():
        if len(name) > 2 and re.search(rf"\b{re.escape(name)}\b", text, re.I):
            out.append(f"the author's name, {name}")
    address = _repository_name(remote)
    if address and address.lower() in text.lower():
        out.append(f"this repository's address, {address}")
    return out


def body(text: str, version: str) -> str:
    """The issue's text: the report without the template's hints, and the toolkit's version."""
    report = re.sub(r"\n{3,}", "\n\n", _clean(text)).strip()
    return f"{report}\n\n---\nSent by an agent, with its user's consent. Toolkit version {version}.\n"


def full_title(title: str) -> str:
    return TITLE_PREFIX + title


def code(title: str, text: str) -> str:
    """Ties a send to the text a preview showed: any change to either gives another code (CLI-33)."""
    return hashlib.sha256(f"{title}\n{text}".encode()).hexdigest()[:8]


def toolkit_version() -> str:
    try:
        return version("syseng")
    except PackageNotFoundError:
        return "unknown"


def send(title: str, text: str) -> str:
    """Open the issue and return its address (CLI-33)."""
    if shutil.which("gh") is None:
        raise RuntimeError("the GitHub CLI (gh) isn't installed")
    done = subprocess.run(["gh", "issue", "create", "--repo", REPOSITORY, "--title", title,
                           "--body-file", "-"], input=text, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or "gh failed")
    return done.stdout.strip()
