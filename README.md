# syseng: a systems-engineering spec toolkit

One engineer directing AI agents on a large codebase reads **requirements**, not code. This toolkit keeps a project's needs, requirements, verification items and decision records in `spec/`, and records how directly a person asked for each one: locked by name, stated, guided, derived from something above, or added by an agent unasked. Agents build fast and reshape what nobody asked for freely; what a person stated or locked comes back to them when a change conflicts with it.

This repository specifies itself with its own toolkit. Run `spec review` and open the page it writes (`.syseng/review.html`): what awaits you, what changed since your last review, the intent captured from your conversations, the items most worth locking, the system as a graph, and the full spec. Copy your feedback from the page and paste it to your agent, or post it on a pull request as your review.

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
- permission rules that let agents run the everyday commands without asking. Claude Code applies a project's rules once you've trusted the folder. `lock`, `resolve` and `migrate` still ask, so you see each command that records what you did;
- a short section in `AGENTS.md`, or `CLAUDE.md`, telling every session to follow the skill. `--no-instructions` leaves those files alone.

For Hermes, add `--harness hermes`: the skill goes in `.agents/skills/syseng/`, and you run `hermes skills trust` once in the repository.

Commit all of these. Agents and hooks run the toolkit as `spec` from your PATH, so install it with `pipx install`, or `uv tool install`, on each machine. To work on the toolkit itself, `pipx install --editable` runs your checkout, so changes apply at once. Run `spec init` again to pick up a newer skill or hook. It leaves your other settings alone, and `spec init --check` reports installed files that are out of date.

## Use

Agents follow the skill, so most of the time you just talk to your agent. The commands:

```sh
spec status           # what's open, what awaits you, and the check's summary
spec check            # everything unfinished in the spec (--todo lists to-dos, --merge before landing a branch)
spec show MODEL-1     # one item: its level of intent, who gave it, its trace, verification and history
spec lock SYS-7 --via chat   # record a person's lock, fingerprinted (`approve` is an alias)
spec review          # write the review page (--against main on a branch; --section NAME for one section as text)
spec diff main       # what changed in the spec since the branch left main (--format yaml for agents)
spec feedback apply  # apply the block copied from the review page; `respond F<n> "…"` answers its comments
spec change show --full      # the open change record, as text
```

What you say about what you want becomes **intent** on the items it directly expresses: a summary close to your words, never a quote, with your name and email, the date and the context. Set who you are once per machine with `git config --global syseng.author "Name <email>"`. In Claude Code, a line of your message that locks items by ID, such as `lock SYS-7, CHECK-3..CHECK-5` or `SYS-7 LGTM`, is recorded as your lock. Anything vaguer gets confirmed first.

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
- `spec/locks.yaml`, `retired.yaml`, `questions.yaml`, `toolkit.yaml`: locks, retired IDs, questions and settings.
- `spec/changes/`: change records, one YAML file per round of changes: every edit with its reason, the conflicts and decisions, and friction reports.

A spec from before intent records (`spec_version: 1`) moves over in two steps: an agent turns each person's words into intent records with `spec edit`, then `spec migrate` does the rest.
