# Skill evals

This repository's tests of its own skill, run on a real agent. Reading a skill says what it asks for; only running it shows whether that changes behaviour. The toolkit runs nothing here: promptfoo runs the evals, and `spec results` reads what it reports, the same as for pytest.

```
nix develop .#evals
evals/run.sh        # three repeats of each case, about $2 of model usage
```

- `promptfooconfig.yaml`: the cases.
- `checks.py`: deterministic checks on what a run left behind.
- `fixture.sh`: builds the project a case runs in.

A verification item links a case by its description. A case passes when 80% of its with-skill runs pass; the without-skill runs are a baseline for you to read. A case that passes both ways shows what the model or the `spec` tool does anyway, not what the skill adds.

Agents run on the host with their tools limited, so this isn't a sandbox: use it for this repository's own skill, not for code you don't trust.

`skill-scenarios.json` holds longer scenarios, not yet converted.
