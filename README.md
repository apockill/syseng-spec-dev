# syseng: a systems-engineering spec toolkit

One engineer directing AI agents on a large codebase reads **requirements**, not code. This toolkit keeps a project's needs, requirements, verification items and decision records in `spec/`. It checks them mechanically and renders them as Markdown views.

This repository specifies itself with its own toolkit. Start with [spec/requirements.md](spec/requirements.md). It's generated, so don't edit it by hand.

## Use

```sh
nix develop path:.        # Python with PyYAML and pytest; `spec` on PATH
spec check                # everything unfinished in the spec (--todo lists to-dos, --merge gates a merge)
spec render               # regenerate spec/requirements.md and spec/decisions.md
spec show MODEL-1         # one item: its trace up to the needs, what refines it, its verification
spec approve SYS-7 --words "approve SYS-7"   # the engineer's approval, fingerprinted
pytest                    # the toolkit's own tests
```

Without Nix, `pip install -e .` gives the same `spec` command.

## Layout

- `spec/elements/<ID>/`: one directory per system element, holding `element.yaml`, `requirements.yaml`, `verification.yaml` and `decisions.yaml`.
- `spec/approvals.yaml`, `retired.yaml`, `questions.yaml`, `toolkit.yaml`: approvals, retired IDs, questions and settings.
- `spec/changes/`: change records, one per round of changes.
- `docs/rules.md`: what each checker rule means and why.
