# syseng: a systems-engineering spec toolkit

One engineer directing AI agents on a large codebase reads **requirements**, not code. This toolkit keeps a project's needs, requirements, verification items and decision records in `spec/`. It checks them mechanically and renders them as Markdown views.

This repository specifies itself with its own toolkit. Start with [spec/requirements.md](spec/requirements.md). It's generated, so don't edit it by hand.

## Install and set up a repository

```sh
pipx install /path/to/syseng-spec-dev   # puts `spec` on your PATH, in its own environment; needs Python 3.11+
cd your-repo
spec init                               # one step: spec/, the skill, Claude Code hooks
```

`spec init` writes:

- `spec/`, with a root system element, if the repository has none;
- `.syseng/hook`, the Claude Code hooks. It uses only Python's standard library, so its guards work even where the toolkit isn't installed;
- the skill, in `.claude/skills/syseng/` (and `.agents/skills/syseng/` with `--harness antigravity`);
- the hooks in `.claude/settings.json`, and two subagents in `.claude/agents/`: an auditor and a reasoning check;
- permission rules that let agents run the everyday commands without asking. Claude Code applies a project's rules once you've trusted the folder. `approve` and `resolve` still ask, so you see each command that records your words;
- a short section in `AGENTS.md`, or `CLAUDE.md`, telling every session to follow the skill. `--no-instructions` leaves those files alone.

For Hermes, add `--harness hermes`: the skill goes in `.agents/skills/syseng/`, and you run `hermes skills trust` once in the repository.

Commit all of these. Agents and hooks run the toolkit as `spec` from your PATH, so install it with `pipx install`, or `uv tool install`, on each machine. To work on the toolkit itself, `pipx install --editable` runs your checkout, so changes apply at once. Run `spec init` again to pick up a newer skill or hook. It leaves your other settings alone, and `spec init --check` reports installed files that are out of date.

## Use

Agents follow the skill, so most of the time you just talk to your agent. The commands:

```sh
spec status           # what's open, what awaits you, and the check's summary
spec check            # everything unfinished in the spec (--todo lists to-dos, --merge before landing a branch)
spec show MODEL-1     # one item: its trace, what refines it, its verification, its history
spec approve SYS-7 --words "approve SYS-7"   # record the engineer's approval, fingerprinted
spec render           # regenerate spec/requirements.md, spec/decisions.md and the change views
```

In Claude Code, a line of your message that approves items by ID, such as `approve SYS-7, CHECK-3..CHECK-5` or `SYS-7 LGTM`, is recorded as your approval. Anything vaguer gets confirmed first.

Agents change the spec only through `spec edit` (see `spec edit --help`). Every edit is logged, with its reason, in the open change record:

```sh
spec change start "what the engineer asked for"   # opens the change record edits are logged in
spec edit <<'YAML'                                 # a batch of add / modify / remove, each with a reason
edits:
  - modify: CLI-3
    set: {text: "The CLI shall …"}
    reason: why
YAML
spec decide --file decision.yaml  # an open decision for the engineer: options, one of them recommended
spec resolve D1 --words "…"       # the engineer's choice (default: the recommended option)
spec friction --workaround "…" --proposal "…"   # tell the engineer what got in your way
spec change close
```

Use a distinctive heredoc delimiter, such as `YAML`, so a batch can't collide with an `EOF` in your own script. When an edit asks for acknowledgments, `spec edit --retry --ack 'ID=note'` sends the same batch again without retyping it.

Verification items link tests as `path::name`: a pytest test (`tests/test_x.py::test_y`) or a GoogleTest (`tests/x_test.cpp::Suite.Test`). The checker confirms each linked test exists.

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
