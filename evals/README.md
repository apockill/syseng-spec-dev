# Skill evals

This repository's tests of its own skill, run on a real agent. Reading a skill says what it asks for; only running it shows whether that changes behaviour. The toolkit runs nothing here: promptfoo runs the evals, and `spec results` reads what it reports, the same as for pytest.

```
nix develop .#evals
evals/run.sh                       # three repeats of each case in both suites
evals/run.sh 5 requirements        # five repeats of one suite
SKILL_BASELINE=main evals/run.sh 5 requirements   # this skill against main's, side by side in one batch
```

- `promptfooconfig.yaml`: the short cases, on the arm project `fixture.sh` builds; the baseline arm has no skill.
- `requirements.yaml`: bringing a whole project into the spec, on the garden-lamp board `lampboard.sh` builds, whose
  code carries the details that used to slip into requirements. A model judges each need and requirement the agent
  wrote; the rubric's examples are the engineer's own corrections. Its baseline arm has no skill, or the skill at
  `SKILL_BASELINE`. Each run takes many minutes.
- `checks.py`: the checks on what a run left behind; all deterministic but the requirement judge.

Compare two versions of the skill side by side in one batch, never one batch before and another after: batches drift.

A verification item links a case by its description. A case passes when 80% of its with-skill runs pass; the without-skill runs are a baseline for you to read. A case that passes both ways shows what the model or the `spec` tool does anyway, not what the skill adds.

Agents run on the host with their tools limited, so this isn't a sandbox: use it for this repository's own skill, not for code you don't trust.

`skill-scenarios.json` holds longer scenarios, not yet converted.
