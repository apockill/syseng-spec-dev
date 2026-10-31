# Test results and verification status

The toolkit runs no tests. The project's own tools or CI run them, and the toolkit reads what they report to work out each verification item's status in each implementation.

## Contents
- Taking in results
- Reading status
- What to do with a failure
- Test links
- Adding a format

## Taking in results

Run `spec results add` once for each step, in any order. Each adds to what's there; reporting a step again on the same revision replaces that step's earlier results. An outcome given with `--id` joins its step instead, so several verdicts can share one. Add reports as they're produced, or pass `--ran-at` when adding an older one: the time decides which result is newest.

```
pytest --junitxml=unit.xml
spec results add unit.xml --format pytest-junit --implementation gcp --step unit

spec results add web/*.xml --format junit --implementation gcp --step frontend

# A step with no report: record its outcome by hand
terragrunt apply && o=pass || o=fail
spec results add --implementation gcp --step infra --id infra/apply --outcome $o

spec results status
```

`--implementation` defaults to the primary one, and `--revision` to version control's current revision. Results go in `.syseng/results`, which version control ignores. In a pipeline whose steps run on separate machines, point `--results-dir` at a shared folder, or pass that folder along as a build artifact, on `status` and `spec review` too.

A reasoning check's or manual item's verdict is a result named by the item's ID: `spec results add --step review --id BOX-V3 --outcome pass`.

## Reading status

`spec results status` shows, per implementation, how many items are passing, failing, not yet run and not implemented (no tests linked for that implementation). It then lists the failures, highest level of intent first; items not run that verify locked requirements; and tests in the results that no item links. `--all` lists every item with the revision it was last tested in, and `--json` gives the same data to a program. It exits with failure when an item is failing, and only then.

An older result still counts: an item says which revision it was last tested in, so you can judge how much that matters. A test's newest result decides, and a skipped test counts as not run.

## What to do with a failure

A failure means the code, the test or the requirement is wrong. Find out which before changing anything. The requirement's level says who decides:
- explicit or stated: the requirement stands. Fix the code, or raise a conflict.
- guided: you may change it, and ask about the change once it's built.
- derived or added: yours to reshape.

Never edit a test only to make it pass.

## Test links

A link in a verification item's `tests` is the identifier its results report: `tests/test_x.py::test_y` from `pytest-junit`, `Suite.Test`-style names from `junit`, or a build target such as `//backend/api:stop_test`. Links that name a file are also checked against the source; other links can only be checked against results, so a link that never appears in them stays not yet run. `spec results status` lists the identifiers it did see that nothing links, which helps when a link doesn't match.

## Adding a format

Formats: `junit`, `pytest-junit`, and `jsonl`, one `{"id": "...", "outcome": "pass"}` per line (pass, fail or skip).

If the project's test tool has no reader, offer to ask for one with a problem report (references/reporting-problems.md) before writing a conversion of your own, so the next project gets it too. Use `jsonl` to keep working meanwhile.

A reader is one new file in `src/syseng/readers/`, with a `read(path, root)` function returning `{identifier: outcome}`; `--format` then takes its name, and nothing else changes.
