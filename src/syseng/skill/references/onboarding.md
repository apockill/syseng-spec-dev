# Bringing an existing project in

Onboarding records what the project is, and why. It doesn't redesign anything. Do as much of the thinking as you can, so the engineer only confirms the needs and everything beneath follows from them.

## Contents
- Checklist
- 1. Preflight
- 2. The tree and the system layer
- 3. Altitude: how detailed a requirement should be
- 4. Drafting, alone or with helpers
- 5. When the code only partly meets a requirement
- 6. Verification and checks
- 7. Handing over

## Checklist

Copy this into your notes and tick it off:

```
- [ ] 1. Preflight: where spec/ will live, what gets published or pushed, who the human author is (raised at the end, not waited on)
- [ ] 2. Element tree and system layer, before any element requirement
- [ ] 3. One small element end to end (pilot)
- [ ] 4. The other elements, each dry-run and checked as it lands
- [ ] 5. Every test linked; every partly-met requirement raised
- [ ] 6. Every automated check run; options and costs for the model-judged checks; coverage reported honestly
- [ ] 7. Questions merged and ranked; review page handed over
```

## 1. Preflight

Don't wait for the engineer: find these out, carry on, and put what needs them at the top of the review page you hand over at the end.
- **Where spec/ would be exposed.** Does the repository publish its directories (a web server serving top-level folders, a docs site)? Does a hook push commits on its own (look in `.git/hooks`)? Is the remote public? The spec will hold the engineer's name and email, and onboarding usually turns up security findings. If any of these would expose it, raise it as the first open decision, and meanwhile don't publish the spec or let a commit push it (`git -c core.hooksPath=/dev/null commit` skips a pushing hook).
- **Who the human author is.** `spec status` says who records are attributed to. If it's an agent account, don't set it yourself from memory or guesswork: raise it as an open decision, and record intent with its source (references/requirement-depth.md, part E) so it can be reattributed.
- **Who wrote the documents.** `git log --format='%an' -- README.md` and similar. Intent read from a document is the engineer's only where they wrote or directed it (part E).

Then run `spec init` (or ask the engineer to) and open the change: `spec change start "Onboard <project>"`. In a repository with several languages or none at its root, set `implementations` in `spec/toolkit.yaml` by hand (references/schema.md).

## 2. The tree and the system layer

Map the system elements from the code's structure first: one tree with the project as the root, `depends_on` for reuse. Good first cuts are what can be deployed, owned or deleted separately (an app, a service, a library). Group thin parts with the same shape into one element. Give an element children where it's too big to read as one.

Then write the system layer yourself, before any element requirement:
- needs, from what the engineer has said and written (see Capturing intent in SKILL.md; documents are guided at most);
- system requirements, each serving needs;
- constraints for rules every part follows (conventions, platforms, languages), so no element restates them.

The system layer is what the engineer reads. Keep it to what they'd recognize; one owner writes it, and helpers never add to it.

## 3. How deep to write

Follow the rules in SKILL.md and references/requirement-depth.md: one requirement per feature, not per function or test; exact values only where the engineer stated them, a safety limit, or a named consumer needs them; repository-wide conventions as system constraints, never restated per element. Where nothing can verify a part (no tests, hardware only), raise the missing verification once, as a decision.

## 4. Drafting, alone or with helpers

Pilot one small element end to end first (requirements, verification items, `spec edit`, `spec check`) to learn the format before scaling out.

For a large project you may hand elements to helper agents. Then:
- give each helper its own output directory for its batch files, never a shared scratch folder, and have it report its findings and proposed decisions in its final message (some harnesses refuse report files from helpers);
- give each the system layer, SKILL.md's rules for how deep to write, references/requirement-depth.md and references/schema.md;
- helpers propose parents and needs; only the owner adds them to the system layer;
- pass on your constraints (what not to touch or run) word for word: helpers don't inherit them;
- review each helper's batch yourself, and dry-run it, before applying it, not after the whole spec is in.

Link every existing test to a verification item. `spec check --todo` lists each Python test no verification item links (V003).

## 5. When the code only partly meets a requirement

Keep the requirement as the project intends it and raise an open decision naming the gap (references/requirement-depth.md, part D). Reword only where your own draft misread what the project intends, and say so in the reason.

## 6. Verification and checks

Run every automated check: the project's tests that can run, `spec check`, and your own listing of unlinked tests.

Don't run the model-judged checks (reasoning checks and auditors) during onboarding yet: how they fit a migration hasn't been specified. Instead, hand the engineer options with costs, so they choose:
- for each option (for example none, the high-value ones you'd pick and why, or every one), how many verification items it covers, roughly how many agents and tokens it takes, and how long;
- what leaving the checks unrun risks: in practice, auditors have found committed secrets, unsafe paths and safety gaps that tests missed.

Report coverage honestly. A reasoning check or manual item that hasn't been run isn't verification yet; say how many ran. A requirement nothing can verify yet gets `verification_deferred` with the reason, or stays a to-do.

Record each failing test or broken link as an open decision. Don't fix it.

## 7. Handing over

Merge related findings into decisions and rank them, most consequential first, each with a recommended option. Every question costs the engineer attention, so merge what one answer would settle. Then tell the engineer:
- the needs to confirm, and the one line that locks them (`lock NEED-1..NEED-n`);
- the ranked questions;
- coverage, how many checks ran, and the options and costs for the model-judged checks;
- the preflight questions (exposure, author) first, since the spec can't be published until they're answered;
- the items most worth locking, highest value first.

Hand over the review page as references/review-and-locks.md says.
