# syseng: a systems-engineering spec toolkit

One engineer directing AI agents on a large codebase reads **requirements**, not code. This toolkit keeps a project's needs, requirements, verification items and decision records in `spec/`. It checks them mechanically and renders them as Markdown views.

This repository specifies itself with its own toolkit. Start with [spec/requirements.md](spec/requirements.md). It's generated, so don't edit it by hand.

## Install and set up a repository

```sh
pip install /path/to/syseng-spec-dev    # or `pip install -e .` from a checkout; needs Python 3.11+
cd your-repo
spec init                               # one step: spec/, the launcher, the skill, Claude Code hooks
```

`spec init` writes:

- `spec/`, with a root system element, if the repository has none;
- `.syseng/spec`, the command agents run the toolkit with, and `.syseng/hook`, the Claude Code hooks;
- the skill, in `.claude/skills/syseng/` (and `.agents/skills/syseng/` with `--harness antigravity`);
- the hooks in `.claude/settings.json`, and two subagents in `.claude/agents/`: an auditor and a reasoning check.

Commit all of these. `spec init` also writes one file outside the repository: this machine's launcher, `~/.config/syseng/launcher`, which says which Python runs the toolkit. If your Python comes from somewhere special, such as a Nix shell, name the command yourself with `--launcher`. Run `spec init` again to pick up a newer skill or hook. It leaves your other settings alone, and `spec init --check` reports installed files that are out of date.

## Use

Agents follow the skill, so most of the time you just talk to your agent. The commands:

```sh
.syseng/spec check            # everything unfinished in the spec (--todo lists to-dos, --merge gates a merge)
.syseng/spec show MODEL-1     # one item: its trace, what refines it, its verification, its history
.syseng/spec approve SYS-7 --words "approve SYS-7"   # record the engineer's approval, fingerprinted
.syseng/spec render           # regenerate spec/requirements.md, spec/decisions.md and the change views
```

In Claude Code, a line of your message that approves items by ID, such as `approve SYS-7, CHECK-3..CHECK-5` or `SYS-7 LGTM`, is recorded as your approval. Anything vaguer gets confirmed first.

Agents change the spec only through `spec edit` (see `.syseng/spec edit --help`). Every edit is logged, with its reason, in the open change record:

```sh
.syseng/spec change start "what the engineer asked for"   # opens the change record edits are logged in
.syseng/spec edit <<'YAML'                                 # a batch of add / modify / remove, each with a reason
edits:
  - modify: CLI-3
    set: {text: "The CLI shall …"}
    reason: why
YAML
.syseng/spec decide --file decision.yaml  # an open decision for the engineer: options, one of them recommended
.syseng/spec resolve D1 --words "…"       # the engineer's choice (default: the recommended option)
.syseng/spec friction --workaround "…" --proposal "…"   # tell the engineer what got in your way
.syseng/spec change close
```

Use a distinctive heredoc delimiter, such as `YAML`, so a batch can't collide with an `EOF` in your own script.

## Working on the toolkit

```sh
pip install -e . pytest && pytest      # the toolkit's own tests
bin/spec check                         # the CLI straight from this checkout
```

If you use Nix, `nix develop` gives a shell with Python, PyYAML and pytest.

## Layout

- `src/syseng/`: the toolkit.
  - `skill/`: the skill `spec init` installs: SKILL.md and its reference pages, including `references/rules.md`, which explains each checker rule.
  - `adapters/`: harness glue: `hook.py` (installed as `.syseng/hook`) and the Claude Code subagents.
- `spec/elements/<ID>/`: one directory per system element, holding `element.yaml`, `requirements.yaml`, `verification.yaml` and `decisions.yaml`.
- `spec/approvals.yaml`, `retired.yaml`, `questions.yaml`, `toolkit.yaml`: approvals, retired IDs, questions and settings.
- `spec/changes/`: change records, one per round of changes.
