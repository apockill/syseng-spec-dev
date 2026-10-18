# Auditors and reasoning checks

The agent that wrote a change shouldn't be the only one checking it. Before the engineer reviews a change, start fresh-context subagents to audit it.
- A fresh subagent isn't a fork, so it doesn't inherit the conversation.
- Give each auditor one task and only the inputs that task needs.
- Each auditor reports findings with evidence.
- Turn the findings into fixes, or into open decisions (`spec decide`).

## The audits

1. **Drift.** Inputs:
   - the change record;
   - the code diff;
   - `spec show` for each system element the change touched.

   Find requirements the code no longer meets, behavior that no requirement covers, and spec edits with no matching code.
2. **Weakened tests.** Inputs: the diffs of tests and verification items that existed before the change and that it modified or deleted. Look for:
   - loosened tolerances;
   - removed assertions or cases;
   - code that special-cases test inputs.

   New tests mostly add coverage. Edited and deleted ones are where weakening hides.
3. **Conformance.** For each changed verification item, compare its description with its linked tests' source. Report what the tests check that the description doesn't mention, and what the description promises that the tests don't check.
4. **Ambiguity.** Do this only for new or changed requirements you judge important, and say why you judge them important.
   - List the plausible readings of the requirement.
   - Write concrete scenarios that tell the readings apart.
   - Ask two or three isolated subagents, who see only the requirement and the scenarios, to predict each outcome.
   - Any disagreement, or any "the requirement doesn't say", is a finding.
5. **Adversarial implementation.** Again, only for requirements you judge important: describe a plausible wrong implementation that would still pass the requirement's verification items. If you can, the verification is too weak.

## Reasoning checks

A reasoning-check verification item is a prompt plus its declared inputs. Run each one this way:
- in a fresh subagent, given only the prompt and the inputs;
- the subagent may read the product's code, but never the spec directory, so the spec can't steer its verdict;
- it returns pass or fail, with evidence quoted from its inputs;
- for an important requirement, take the majority verdict of three independent runs.

Harness adapters provide ready-made auditor and reasoning-check subagents where the harness supports them. Otherwise, set them up yourself to these specifications.
