# Skill evals

`plugin/` packages the skill so `claude plugin eval` can run it on a real model. Each case in `plugin/evals/` is a prompt and its graders; a verification item links a case by name.

```
cd evals/plugin
claude plugin eval . --runs 3 --model sonnet --max-cost-usd 3 -j 4 --trust-plugin --no-publish --json /tmp/eval.json
cd ../..
spec results add /tmp/eval.json --format claude-plugin-eval --step evals
```

Each case also runs without the skill. A case that passes both ways shows what the model does anyway, not what the skill adds, so read the delta too. These runs count against your usage: about $1 for the four cases at three runs each.

`skill-scenarios.json` holds longer scenarios, not yet converted.
