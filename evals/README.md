# Skill evals

These run the skill on a real agent and check what it does. Reading a skill says what it asks for; only running it shows whether that changes behaviour.

```
nix develop .#evals
evals/run.sh        # three repeats of each case, about $2 of model usage
```

| File | What it is | Tied to a runner? |
|---|---|---|
| `evals.json` | The cases, in the Agent Skills format, plus `checks` | No |
| `checks.py` | Deterministic checks on what a run left behind | No |
| `fixture.sh` | Builds the project a case runs in | No |
| `runners/promptfoo/` | Turns the above into a promptfoo run | Yes |
| `src/syseng/readers/promptfoo.py` | Reads its results into `spec results` | Yes |

To try another runner, add a folder under `runners/` and a reader, and leave the cases alone. To drop one, delete those two.

A verification item links a case by its `id`. A case passes when 80% of its with-skill runs pass; the without-skill runs are a baseline for you to read. A case that passes both ways shows what the model or the `spec` tool does anyway, not what the skill adds.

Agents run on the host with their tools limited, so this isn't a sandbox: use it for this repository's own skill, not for code you don't trust.

`skill-scenarios.json` holds longer scenarios, not yet converted.
