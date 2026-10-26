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
- [ ] 1. Preflight: where spec/ will live, what gets published or pushed, who the human author is
- [ ] 2. Element tree and system layer, before any element requirement
- [ ] 3. One small element end to end (pilot)
- [ ] 4. The other elements, each dry-run and checked as it lands
- [ ] 5. Every test linked; every partly-met requirement raised
- [ ] 6. Every automated check run; options and costs for the model-judged checks; coverage reported honestly
- [ ] 7. Questions merged and ranked; review page handed over
```

## 1. Preflight

Before `spec init` or any edit, find out:
- **Where spec/ would be exposed.** Does the repository publish its directories (a web server serving top-level folders, a docs site)? Does a hook push commits on its own (look in `.git/hooks`)? Is the remote public? The spec will hold the engineer's name and email, and onboarding usually turns up security findings. If any of these would expose it, stop and ask the engineer before creating spec/ or committing.
- **Who the human author is.** `spec status` says who records are attributed to. If it's an agent account, ask the engineer to set `git config syseng.author`. Don't set it from memory or guesswork.
- **Who wrote the documents.** `git log --format='%an' -- README.md` and similar. Intent read from a document is the engineer's only where they wrote or directed it.

Then run `spec init` (or ask the engineer to) and open the change: `spec change start "Onboard <project>"`. In a repository with several languages or none at its root, set `implementations` in `spec/toolkit.yaml` by hand (references/schema.md).

## 2. The tree and the system layer

Map the system elements from the code's structure first: one tree with the project as the root, `depends_on` for reuse. Good first cuts are what can be deployed, owned or deleted separately (an app, a service, a library). Group thin parts with the same shape into one element. Give an element children only where it's too big to read as one, and only along seams its tests already follow.

Then write the system layer yourself, before any element requirement:
- needs, from what the engineer has said and written (see Capturing intent in SKILL.md; documents are guided at most);
- system requirements, each serving needs;
- constraints for rules every part follows (conventions, platforms, languages), so no element restates them.

The system layer is what the engineer reads. Keep it to what they'd recognize; one owner writes it, and helpers never add to it.

## 3. Altitude: how detailed a requirement should be

Write one requirement per behaviour that a user, an operator or another element relies on. Not one per function, branch or test.

- **Constants stay out of requirements.** Timeouts, retry counts, poll intervals and thresholds go in the verification item's description or a decision record, unless the engineer stated the number or it's a safety limit.
  - Too deep: "When asked to power off, the supervisor shall stop the arm, wait 0.3 seconds and repeat the power-off up to 6 times until the arm reads unpowered."
  - Right: "When asked to power off, the supervisor shall confirm the arm reads unpowered, and raise an alarm naming the e-stop when it doesn't."
- **Size:** about 5 to 15 requirements per element. Past 30, the element needs children or the requirements are too fine.
- **Where nothing can verify it** (no tests, hardware only), write fewer and coarser requirements, and raise the missing verification once, as a decision.
- **Flow-down:** an element's requirement refines one of its parent's. When an element gets children, give it a few requirements of its own for them to refine, stated as what the element does as a whole, not as placeholders.

## 4. Drafting, alone or with helpers

Pilot one small element end to end first (requirements, verification items, `spec edit`, `spec check`) to learn the format before scaling out.

For a large project you may hand elements to helper agents. Then:
- give each helper its own output directory, never a shared scratch folder;
- give each the system layer, the altitude rule above and references/schema.md;
- helpers propose parents and needs; only the owner adds them to the system layer;
- pass on your constraints (what not to touch or run) word for word: helpers don't inherit them;
- review each helper's batch yourself, and dry-run it, before applying it, not after the whole spec is in.

Link every existing test to a verification item. `spec check` doesn't list unlinked tests yet: list the test functions yourself and compare.

## 5. When the code only partly meets a requirement

Keep the requirement as the project intends it, and raise an open decision naming the gap. Don't reword the requirement to match the code: that turns a bug into a spec. Never narrow a safety rule to fit the code.

Reword only where your own draft was wrong about what the project intends (a misread number, a wrong condition), and say so in the reason.

## 6. Verification and checks

Run every automated check: the project's tests that can run, `spec check`, and your own listing of unlinked tests.

Don't run the model-judged checks (reasoning checks and auditors) during onboarding yet: how they fit a migration hasn't been specified. Instead, hand the engineer options with costs, so they choose:
- for each option (for example none, the high-value ones you'd pick and why, or every one), how many verification items it covers, roughly how many agents and tokens it takes, and how long;
- what leaving the checks unrun risks: in practice, auditors have found committed secrets, unsafe paths and safety gaps that tests missed.

Report coverage honestly. A reasoning check or manual item that hasn't been run isn't verification yet; say how many ran. A requirement nothing can verify yet gets `verification_deferred` with the reason, or stays a to-do.

Record each failing test or broken link as an open decision. Don't fix it.

## 7. Handing over

Merge related findings into decisions and rank them, most consequential first: aim for no more than about 15 questions, each with a recommended option. Then tell the engineer:
- the needs to confirm, and the one line that locks them (`lock NEED-1..NEED-n`);
- the ranked questions;
- coverage, how many checks ran, and the options and costs for the model-judged checks;
- anything from the preflight that needs them before the spec is committed or published.

Hand over the review page as references/review-and-locks.md says.
