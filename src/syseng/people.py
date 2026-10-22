"""Who a record names: the person behind each intent record and lock (SYS-43, CLI-11, DR-56).

On a machine where an agent commits under its own account, version control's user is the
agent, so the person comes first from a setting of their own:

  1. `git config syseng.author "Name <email>"`, set per machine and per person, never committed;
  2. the SYSENG_AUTHOR environment variable;
  3. version control's own `user.name` and `user.email`;
  4. the login name.
"""

import getpass
import os
import subprocess
from pathlib import Path

SETTING = "syseng.author"
ENV = "SYSENG_AUTHOR"


def _git(repo: Path, key: str) -> str:
    try:
        return subprocess.run(["git", "config", key], cwd=repo, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def person(repo: Path) -> tuple[str, str]:
    """The person to record, and where that came from."""
    setting = _git(repo, SETTING)
    if setting:
        return setting, f"git config {SETTING}"
    env = os.environ.get(ENV, "").strip()
    if env:
        return env, f"${ENV}"
    name, email = _git(repo, "user.name"), _git(repo, "user.email")
    if name or email:
        return (f"{name} <{email}>" if name and email else name or email), "git config user.name and user.email"
    return getpass.getuser(), "the login name"


def is_set(repo: Path) -> bool:
    """Whether the person has a setting of their own, rather than falling back to version control's user."""
    return bool(_git(repo, SETTING) or os.environ.get(ENV, "").strip())
