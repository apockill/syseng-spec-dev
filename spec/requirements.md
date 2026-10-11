# Requirements, round 1

*Draft of 2026-10-11.* This is the first spec for this toolkit, written as an exercise in the workflow it describes. It is one file so it can be reviewed in one sitting. Once the spec format is settled (Q1), it splits into per-component directories (MODEL-1). Verification items come in a later round.

## How to read this

- ✅ **CONFIRMED**: states something you asked for. The quote under it is my source. Skim it to check I didn't stretch your words.
- 🟡 **NEEDS REVIEW**: I added it, or I added substance to something you asked for (a number, a mechanism, a scope). *Why* gives my reasoning, and *Refines* names the ask it builds on. These are the places I'm steering, so these are the ones to read.

**63 confirmed · 46 need review · 10 open questions.** Suggested order: the open questions, then the 🟡 items. The ✅ items are skimmable.

## Open questions

These came up while I was writing the requirements down. Some are conflicts between your own asks that only showed once the asks sat side by side.

1. **How do agents edit the spec?** (MODEL-1, CLI-1) You first leaned toward JSON that agents touch only through the CLI. I proposed plain YAML that agents edit directly, with the CLI for queries, checks and to-do lists. This choice decides the file layout and most of the CLI.
2. **What runs at merge?** (VERIFY-7) I read "changed VIs belonging to changed REQs/components" as three groups: items that changed, items that verify a changed requirement, and items of components whose related code changed. Is the third group in?
3. **When do auditors run?** (AGENT-4, VERIFY-6) Your code-first flow runs skeptical audits before your review. Your tiering holds token-heavy work until after your LGTM, and audits are token-heavy.
   - *Before review:* the audits inform what you read, but they spend tokens on changes you might reject.
   - *After LGTM:* cheaper, but you approve without seeing their findings.

   My lean: before.
4. **Stop or continue on a contradiction?** (AGENT-17) When a request contradicts an approved requirement, should the agent ask right away or note it and raise it at review? Asking right away gives you earlier steering but interrupts "make X happen". My lean: ask right away only when the requirement is critical.
5. **How do reasoning checks run?** (REASON-2) Subagents running inside the session may inherit repo instruction files and memory, which breaks the zero-context rule. Calling the model API from the Python CLI controls the context and model version exactly, but it needs an API key and runs outside Claude Code. Which?
6. **What does accepting a failed reasoning test change?** (AGENT-9) Suppose the behavior you accepted also contradicts the requirement's text. Should the requirement change too, which would then show up as a bright change in the diff? My lean: yes. Otherwise the requirement and its VI end up saying different things.
7. **What exactly counts as approval?** (CHANGE-6, CHANGE-7)
   - In spec-first mode, your lgtm on the spec diff is recorded on the branch. Merging then approves the final result, including any deviations.
   - In code-first mode, merging is the only approval.

   Either way: does a merge approve every agent-proposed requirement in it, or do you want to sign off individually on ones you only skimmed? My lean: the merge approves them, and their origin (MODEL-14) stays on record so you can audit them later.
8. **Who may write needs?** (MODEL-12) Needs sit at the top of every trace. An agent-invented need could justify agent-invented requirements beneath it. My lean: only you write needs, and agents propose them to you as questions.
9. **Are long-running tests expensive?** (MODEL-9) Your tiers split on token cost. By that rule an hour-long integration test is cheap, so it would run on every check. Should the expensive tier also cover slow items?
10. **Which mode applies when a request doesn't say?** (CHANGE-1, CHANGE-2) "Write the specs for X" is spec-first, and "build it real quick" is code-first. "Make X happen" says neither. My lean: code-first, so the common case asks nothing of you.

## Components

| ID | Component | Parent | Depends on |
|---|---|---|---|
| SYS | The toolkit as a whole | — | — |
| MODEL | What a spec contains | SYS | — |
| CHECK | The checker (the linter) | SYS | MODEL, LANG, CHANGE, VERIFY |
| VERIFY | Runs verification items and tracks their status | SYS | MODEL, LANG |
| UNIT | Unit-test modality | VERIFY | LANG |
| INTEG | Integration-test modality | VERIFY | REASON |
| REASON | Reasoning-test modality | VERIFY | — |
| LANG | Language adapters | SYS | — |
| CHANGE | Change records and modes | SYS | MODEL |
| REVIEW | Review pages | SYS | MODEL, CHANGE, VERIFY |
| CLI | The command-line tool | SYS | MODEL, CHECK, VERIFY, REVIEW |
| AGENT | Skills, subagents and hooks | SYS | CLI |

---

## SYS: the toolkit

A reusable systems-engineering toolkit. It provides skills, subagents, a checker, a verification runner and review pages, so that one engineer can direct AI agents on a large codebase by reading requirements instead of code.

### Needs

- ✅ **NEED-1** The engineer needs to keep intellectual control of a product of 100,000+ lines of code by reading its requirements, and only occasionally its verification items.
  - *Source:* "allow a single engineer to maintain intellectual control over what they are building, even as the product balloons to 100k+ LOC … only showing the highest signal things (REQs). VERs are more for the LLMs … and also for the sole engineer to read occasionally"
- ✅ **NEED-2** The engineer needs agents to surface the questions that spec work raises, so the engineer gets more chances to steer.
  - *Source:* "for the LLM to stop and say 'wait, actually, now that I am forced to think in this way it begs the questions XYZ' those questions can be surfaced to the user, who now has more opportunities to steer"
- ✅ **NEED-3** The engineer needs to reuse the toolkit across unrelated projects.
  - *Source:* "this skill/set of skills must NOT reference [the host project]. I plan on reusing this."
- ✅ **NEED-4** The engineer needs the V&V documentation to be enough to rebuild the product in another language.
  - *Source:* "if I took all the V&V documentation and said 'build this in rust' I'd want that to work"
- ✅ **NEED-5** The engineer needs the process to cost the main agent little attention.
  - *Source:* "How to make this system relatively low overhead, so that the agent I'm interfacing with doesn't have to think about it much"
- ✅ **NEED-6** The engineer needs to choose, per change, between specifying first and building first.
  - *Source:* "the system should support two CUJs … We want to support both workflows cleanly."

### Requirements

- ✅ **SYS-1** The toolkit's skills, subagent definitions, code and documentation shall contain no references to a specific host project.
  - *Source:* NEED-3.
- ✅ **SYS-2** This repository shall pass the toolkit's checker against its own spec.
  - *Source:* "that repo should dogfood this methodology. We should be writing this tooling with our own system engineering tooling, and linting it"
- ✅ **SYS-3** The toolkit shall be implemented in Python.
  - *Source:* "likely the CLI would be written in python"
- 🟡 **SYS-4** The toolkit shall read every project-specific setting from a configuration file in the host repository.
  - *Why:* this is the counterpart to SYS-1. Project specifics (implementations, test commands, banned terms) need a home outside the skills.
- 🟡 **SYS-5** The toolkit shall install into a host repository as one package containing its skills, subagent definitions, hooks and CLI.
  - *Why:* reusing the toolkit (NEED-3) shouldn't mean copying four kinds of file by hand. A Claude Code plugin bundles exactly these four.

## MODEL: what a spec contains

A spec holds components, needs, requirements, verification items and implementations, plus the links between them.

- ✅ **MODEL-1** The spec shall store each component as its own directory inside a single, flat components directory.
  - *Source:* "We have a directory called components and inside that we have directories for each component … It's still a flat directory"
- ✅ **MODEL-2** The spec model shall support components at every level, from the whole product down to a single unit.
  - *Source:* "these range from extremely high level to extremely small level"
- ✅ **MODEL-3** Each component shall list the components it depends on.
  - *Source:* "These components state their dependencies in some way … A component could be depended on by many other components."
- ✅ **MODEL-4** The component dependency graph shall contain no cycles.
  - *Source:* "the linter should enforce that there's no loops"
- ✅ **MODEL-5** The spec shall hold requirements and verification items as separate kinds of item, with each verification item linked to the requirements it verifies.
  - *Source:* "We have the concept of requirements and verification items."
- ✅ **MODEL-6** Each verification item shall describe its check in terms independent of any programming language.
  - *Source:* "if there are tests they should describe the test and link to the 'implementations'"
- ✅ **MODEL-7** The spec shall name each implementation of the product, with its language.
  - *Source:* "it could be 'implemented in {Implementation name XYZ, C++} or have no implementations'"
- ✅ **MODEL-8** Each verification item shall link to its tests separately for each implementation.
  - *Source:* "there's an implementation of this for the C++ stack, but if I remade it in rust that could also work"
- ✅ **MODEL-9** Each verification item shall have a cost tier: cheap (fully automated, no model calls) or expensive (needs model calls or subagents).
  - *Source:* "Expensive (e.g. not fully automated steps that require extra tokens/subagents spun up) should be a separate tier of tests". See Q9.
- ✅ **MODEL-10** Each component shall list its related code by path or pattern, with no limit on how many components a file relates to.
  - *Source:* "Should we decouple it, such that components can call out related code files" · "I'm not sure about 1 file to 1 component"
- 🟡 **MODEL-11** Each component except the root shall name exactly one parent component, recorded separately from its dependencies.
  - *Why:* "is part of" (home feed → side panel) and "depends on" (side panel → image cache) are different relations. Requirements flow down the first, and change impact flows along the second. If the two are mixed, neither works.
- 🟡 **MODEL-12** The spec shall hold needs, meaning goals that can't be verified directly, as a third kind of item, each traced to the requirements that serve it.
  - *Why:* top-level goals such as NEED-1 can't be tested, and forcing them into "shall" form produces fake precision. This document already uses needs. See Q8.
- 🟡 **MODEL-13** Each requirement shall carry a rationale.
  - *Why:* the rationale is the first thing an agent reads when you ask why a requirement exists. That's why the NASA and INCOSE handbooks make it mandatory.
- 🟡 **MODEL-14** Each requirement shall record its origin: stated by the engineer, or proposed by an agent.
  - *Refines:* "we may want to consider adding this functionality to the rendering UI, so I know what to read"
  - *Why:* makes this document's ✅/🟡 split permanent, so REVIEW-8 can show it.
- 🟡 **MODEL-15** A requirement ID shall never be reused, including after its requirement is deleted.
  - *Why:* "why did AGENT-17 disappear?" only works if AGENT-17 has always meant one thing.
- 🟡 **MODEL-16** Requirement text shall follow the wording rules: exactly one "shall", one of the EARS (Easy Approach to Requirements Syntax) sentence patterns, and no banned terms (vague words, escape clauses, open-ended endings, test or implementation vocabulary).
  - *Why:* these are the mechanically checkable core of INCOSE's *Guide to Writing Requirements*. Short, unambiguous requirements are what make NEED-1 cheap. Banning test vocabulary is how a requirement avoids stating its test.
- 🟡 **MODEL-17** Requirement and need text shall contain no language-specific names, such as function, class or file names.
  - *Why:* NEED-4. A requirement that names a C++ class can't guide a Rust rebuild. Those names belong in test links and related-code lists.
- 🟡 **MODEL-18** Each requirement shall have at least one verification item, or a recorded reason for having none.
  - *Why:* a requirement that nothing checks is only a wish. The recorded reason lets you accept a gap on purpose.
- 🟡 **MODEL-19** Each requirement shall have a criticality: normal or critical.
  - *Why:* lets rigor scale with importance. "This invariant really matters" becomes a criticality change that triggers stronger rules (MODEL-20, REASON-4, AGENT-15, AGENT-16), instead of every requirement paying that cost.
- 🟡 **MODEL-20** Each critical requirement shall have verification items of at least two different modalities.
  - *Why:* one method gives one view of a requirement. Two methods, such as a unit test plus a reasoning test, fail in different ways.
- 🟡 **MODEL-21** Each implementation shall declare a root directory, under which its related-code paths and test links resolve.
  - *Why:* lets a C++ original and a Rust port share one repository, each with its own code lists and tests.
- 🟡 **MODEL-22** Exactly one implementation shall be marked primary.
  - *Why:* gives changes a default target (CHANGE-8).

## CHECK: the checker

The checker tells an agent everything still unfinished in its spec work, deterministically and within seconds.

- ✅ **CHECK-1** In a single run, the checker shall report every violation of the MODEL requirements, along with every finding of the checks below.
  - *Source:* "the linter will be as comprehensive as possible to flag to the AI that its job is not done yet"
  - *Reworded:* "as comprehensive as possible" is an escape clause by INCOSE's rules, because nothing could ever fail it. This version can fail.
- ✅ **CHECK-2** Each finding shall state what is wrong, where it is, and what action resolves it, in terms an agent can act on without the methodology docs in its context.
  - *Source:* "a lot of the time the AI will not have the document for the system engineering documentation in its context … flag to the AI that its job is not done yet. That certain documentation needs to be updated, that certain tests need to be linked"
- ✅ **CHECK-3** The checker shall report each test that no verification item links to.
  - *Source:* "every unit test is referenced in some file" · "XYZ tests have been added and are not associated with VERs"
- ✅ **CHECK-4** The checker shall report each verification-item link to a test or file that does not exist.
  - *Source:* "XYZ tests are referenced in VERs but don't exist"
- ✅ **CHECK-5** When a component's related code has changed and its requirements have not, the checker shall report that component together with its current requirements.
  - *Source:* "XYZ files were edited but the REQs not updated, can you check the REQs" · "if the code is changed then the agent is notified … and dumps all the specs into context"
- ✅ **CHECK-6** When a verification item has changed and none of the requirements it verifies has, the checker shall ask whether a requirement change was forgotten.
  - *Source:* "hey, you had to change a verification item but didn't change a req - did you forget?"
- 🟡 **CHECK-7** The checker shall treat a CHECK-5 or CHECK-6 finding as resolved once the change record gives a reason for it.
  - *Refines:* "Then it should file a waiver (maybe?) or just continue"
  - *Why:* "just continue" leaves you nothing to read. A one-line reason costs the agent little, and it's what you'll want to see in review.
- 🟡 **CHECK-8** The checker shall report each changed code file that no component lists as related.
  - *Refines:* "every header is referenced in some file"
  - *Why:* a soft version of your original guarantee that still works without a one-file-one-component rule. New code can't land outside every component's view without a finding.
- 🟡 **CHECK-9** When a linked test's source or a verification item's description changes without the pair being re-confirmed, the checker shall report the pair.
  - *Why:* keeps descriptions and tests from drifting apart silently. The checker fingerprints both sides. Re-confirming means an agent has checked that they still match and recorded that it did.
- 🟡 **CHECK-10** The checker shall report a verification item that has no tests in an implementation as a to-do for that implementation, not as a finding.
  - *Why:* in spec-first planning and in a port, unimplemented items are expected. They belong on the to-do list (CLI-2). CHECK-11 decides when they must be finished.
- 🟡 **CHECK-11** When an agent marks a change done, the checker shall report each requirement the change added or modified that neither passes in the change's target implementation nor has a recorded deferral.
  - *Why:* one completion rule for both modes. A deferral and its reason cover features built across several changes, and ports.
- 🟡 **CHECK-12** The checker shall finish within 5 seconds on a 100,000-line repository on the engineer's development machine.
  - *Why:* the checker runs every time an agent tries to finish (AGENT-12), and slow checks get skipped.
- 🟡 **CHECK-13** Where a repository adopts the toolkit with existing code, the checker shall accept a baseline of pre-existing findings and report only findings outside it.
  - *Why:* an existing codebase starts with hundreds of unlinked tests, and a baseline makes adoption gradual. The baseline should only ever shrink.

## VERIFY: the verification runner

The runner executes verification items by modality and tier, and tracks each item's status in each implementation.

- ✅ **VERIFY-1** Adding a verification modality shall require no change to the runner's existing code.
  - *Source:* "Let's allow for different modalities of tests, and make it extensible."
- ✅ **VERIFY-2** The runner shall support three modalities in its first release: unit test, integration test and reasoning test.
  - *Source:* "'software unit test'" · "'REASONING TEST'" · "'INTEGRATION TEST'"
- ✅ **VERIFY-3** The runner shall run independent verification items in parallel.
  - *Source:* "the skill has a tool for running these in parallel and reporting back"
- ✅ **VERIFY-4** After each run, the runner shall report each verification item's result.
  - *Source:* as VERIFY-3.
- ✅ **VERIFY-5** The runner shall derive each verification item's status in each implementation: not implemented, not yet run, passing or failing.
  - *Source:* "the specs should mark in some way what has been implemented yet, and what has not (e.g. don't expect tests to pass, perhaps VIs have been specced but not implemented)"
- ✅ **VERIFY-6** The runner shall run expensive-tier items only after the engineer has approved the change for merging.
  - *Source:* "only run when the user already agrees the system LGTM, and it's time to merge things to main"
- ✅ **VERIFY-7** When preparing a merge, the runner shall run the expensive-tier items the change affects: items that changed, items that verify a changed requirement, and items of components whose related code changed.
  - *Source:* "run all the test suite (for changed VIs belonging to changed REQs/components, so as to not waste too many tokens)". The three groups are my reading; see Q2.
- ✅ **VERIFY-8** When an expensive-tier item fails, the runner shall add the failure to the change's list of decisions for the engineer.
  - *Source:* "If reasoning or integration+reasoning tests fail, the LLM should add it to a list of things to flag to the user."
- 🟡 **VERIFY-9** When preparing a merge, the runner shall run every cheap-tier item.
  - *Why:* cheap items cost seconds, not tokens. Running only some of them saves little and risks missing a regression.
- 🟡 **VERIFY-10** When preparing a merge, the runner shall use a reasoning check to compare each changed verification item's tests against its description.
  - *Why:* CHECK-9 catches drift mechanically. This catches a test that never matched its description in the first place.

### UNIT: unit-test modality (child of VERIFY)

- ✅ **UNIT-1** The unit-test modality shall run a verification item's linked tests through the language adapter of each implementation that has them.
  - *Source:* "one modality might be 'software unit test', and can be written in [supported languages]"

### INTEG: integration-test modality (child of VERIFY)

- ✅ **INTEG-1** An integration-test item shall run its declared commands.
  - *Source:* "'INTEGRATION TEST' which would be a combination of 'run XYZ COMMANDS'"
- ✅ **INTEG-2** Where an integration-test item declares a reasoning step, the modality shall judge the commands' output with a reasoning check.
  - *Source:* "and perhaps 'REASON' about them"
- 🟡 **INTEG-3** An integration-test item shall pass only when each command's exit status and output meet the item's declared expectations.
  - *Why:* without declared expectations, "passed" only means "didn't crash".

### REASON: reasoning-test modality (child of VERIFY)

- ✅ **REASON-1** A reasoning-test item shall consist of a prompt asking a model to judge a stated aspect of the product, plus the inputs that judgment needs.
  - *Source:* "'REASONING TEST' which is a prompt that asks an LLM to reason about certain aspects we want to think about, that might be hard to confirm"
- ✅ **REASON-2** The modality shall run each reasoning check with only its item's prompt and declared inputs in context: no project instructions, memory or conversation history.
  - *Source:* "Subagents that do reasoning should be spun up with 0 context about the project, and only given what is absolutely necessary to verify … (this should be a req)". See Q5.
- 🟡 **REASON-3** Each reasoning check shall return a pass or fail verdict with evidence quoted from its inputs.
  - *Why:* a bare verdict can't be audited. Quoted evidence shows you why it failed within seconds.
- 🟡 **REASON-4** For an item that verifies a critical requirement, the modality shall take the majority verdict of three independent runs.
  - *Refines:* "the goal being to have slightly more deterministic results"
  - *Why:* one sample from a nondeterministic judge tells you little, and three runs is the smallest number that gives a majority. Limiting this to critical requirements keeps the token cost down.

## LANG: language adapters

The adapters hold everything specific to a programming language: finding tests, running them and reading their source.

- ✅ **LANG-1** Adding a language shall require only a new adapter, with no change to existing adapters or the core.
  - *Source:* "adding rust later is a matter of 'extending' rather than 'refactoring' the cli tool"
- ✅ **LANG-2** The toolkit shall include adapters for C++ and Python.
  - *Source:* "The commandline interface the LLM uses would support C++ to start with" · "one language we should support as a P0 should also be python"
- 🟡 **LANG-3** Each adapter shall provide three operations: list a repository's tests, run a chosen set of tests, and return a named test's source.
  - *Why:* this is the minimum that CHECK-3, CHECK-9 and UNIT-1 need. Coverage collection can come later as an optional fourth operation.
- 🟡 **LANG-4** The first-release adapters shall support GoogleTest for C++ and pytest for Python.
  - *Why:* these are the most common frameworks in each language. Others (Catch2, unittest) can come later as adapter options.

## CHANGE: change records and modes

The change record captures what was asked, which mode the change runs in, what changed in the spec and why, and what needs the engineer's decision.

- ✅ **CHANGE-1** The toolkit shall support a spec-first mode, in which the engineer approves the spec changes before implementation begins.
  - *Source:* "the engineer wants to know BEFORE the code is written how the specs will be built … I then examine the diff and agree 'lgtm', then the implementation is created"
- ✅ **CHANGE-2** The toolkit shall support a code-first mode, in which the agent implements first and then updates the spec to match.
  - *Source:* "hey build it real quick, then update the spec to match"
- ✅ **CHANGE-3** Each change record shall keep a list of decisions for the engineer.
  - *Source:* "the LLM should add it to a list of things to flag to the user"
- 🟡 **CHANGE-4** Each change record shall capture the engineer's request in the engineer's own words.
  - *Why:* lets auditors ask "you asked for X, so why does the spec now also say Y?" without a separate planning step.
- 🟡 **CHANGE-5** Each change record shall give a reason for each requirement the change added, modified or removed.
  - *Refines:* "I view the spec diff and say 'hey why does this component no longer have a requirement to do x or y' and the agent is able to explain"
  - *Why:* an agent starting from a fresh context months later can only answer "why?" if someone wrote the reason down at the time.
- 🟡 **CHANGE-6** In spec-first mode, the change record shall store the spec revision the engineer approved.
  - *Why:* AGENT-11 and REVIEW-11 compare the final spec against this revision to find deviations. See Q7.
- 🟡 **CHANGE-7** The toolkit shall treat a spec edit as approved once it is merged into the main branch.
  - *Why:* gives "approved" a precise meaning without extra tooling: your merge is the approval. Auditors check changes against the approved spec.
- 🟡 **CHANGE-8** Each change record shall name the implementation the change targets, defaulting to the primary implementation.
  - *Why:* CHECK-11 and the to-do list need to know which implementation "done" refers to. For a port, it's the new implementation.

## REVIEW: review pages

Web pages for the engineer, showing the spec as a whole and how a change alters it.

- ✅ **REVIEW-1** The renderer shall render the spec's components and requirements as a web page.
  - *Source:* "we'll create tools to render components on a web page"
- ✅ **REVIEW-2** The renderer shall render the spec differences between two revisions as a web page.
  - *Source:* "and also render the diffs between changes"
- ✅ **REVIEW-3** The renderer shall hide verification items until the engineer asks to see them.
  - *Source:* "only showing the highest signal things (REQs). VERs are … for the sole engineer to read occasionally"
- ✅ **REVIEW-4** In a diff, the renderer shall highlight brightly each component whose requirements changed.
  - *Source:* "bright colors when a component has changed requirements"
- ✅ **REVIEW-5** In a diff, the renderer shall highlight mildly each component whose related code changed while its requirements and verification items did not.
  - *Source:* "mild color when a component's underlying file changed but the req/ver didn't"
- ✅ **REVIEW-6** In a diff, the renderer shall leave unchanged components unhighlighted.
  - *Source:* "nothing if nothing changed"
- ✅ **REVIEW-7** The renderer shall show each requirement's status in each implementation.
  - *Source:* "the specs should mark in some way what has been implemented yet, and what has not"
- 🟡 **REVIEW-8** In a diff, the renderer shall mark each new or changed requirement that an agent proposed.
  - *Refines:* "we may want to consider adding this functionality to the rendering UI, so I know what to read"
- 🟡 **REVIEW-9** In a diff, the renderer shall highlight in amber each verification item that changed while the requirements it verifies did not.
  - *Why:* that's where test weakening hides. In a 2025 benchmark, Claude models cheated mostly by editing test files, so this case deserves its own color.
- 🟡 **REVIEW-10** In a diff, the renderer shall show the recorded reason beside each changed or removed requirement.
  - *Why:* answers most "why?" questions before you need to ask them.
- 🟡 **REVIEW-11** For a spec-first change, the renderer shall show the differences between the approved spec and the final spec.
  - *Why:* puts your "I had to change a few things for you to review" on the page, not just in a chat message.
- 🟡 **REVIEW-12** In a diff, the renderer shall show the decisions for the engineer above all requirement changes.
  - *Why:* those decisions are the steering points (NEED-2), so they shouldn't be buried at the bottom.

## CLI: the command-line tool

The single tool through which agents, and the engineer, query, check, verify and render the spec.

- ✅ **CLI-1** The toolkit shall provide one command-line tool through which agents query, check, verify and render the spec.
  - *Source:* "The commandline interface the LLM uses" · "the only way that the LLM interacts with components is through a command line tool". See Q1.
- ✅ **CLI-2** The CLI shall generate, for a named implementation, a to-do list of the requirements and verification items not yet implemented or not passing in it.
  - *Source:* "This ends up forming an automated 'todo' list for the LLM … 'let's implement this project in rust' and the todo list can be regenerated but for an entire different implementation"
- 🟡 **CLI-3** The CLI shall answer four queries: one component's spec, the components related to given files, the trace from a requirement to its verification items and tests, and a requirement's change history.
  - *Why:* lets an agent pull exactly the spec it needs into context, instead of all of it. This is your "dumps the specs into context", but targeted.
- 🟡 **CLI-4** The CLI shall order a to-do list so that each component's items follow those of the components it depends on.
  - *Why:* lets an agent build from the bottom up. A port starts at the leaf components and works upward.

## AGENT: skills, subagents and hooks

These fit the methodology into an agent's normal coding work.

- ✅ **AGENT-1** In code-first mode, the skill shall let the main agent edit code without first reading the spec.
  - *Source:* "it spends time looking at code, and WHEN IT ADDS VALUE also reading the current REQs and V&V, but otherwise … it probably doesn't need to"
- ✅ **AGENT-2** The skill shall direct the main agent to update the requirements and verification items a change affects, as part of that change.
  - *Source:* "It makes all the changes and tries its best to update V&V along the way."
- ✅ **AGENT-3** The main agent shall report a change as done only after the checker reports no findings for it.
  - *Source:* "At the end, it runs the linter and is told 'hey XYZ tests have been added and are not associated with VERs …'"
- ✅ **AGENT-4** Skeptical auditor subagents shall review each change's spec updates before the engineer reviews the change.
  - *Source:* "have skeptical subagents run audits too, to ensure everything is up to date. Then I go in, read the specs". See Q3.
- ✅ **AGENT-5** The toolkit shall critique each new or changed requirement and verification item.
  - *Source:* "How do we write some way to critique whether or not a requirement is well written or whether or not a verification item is well written"
- ✅ **AGENT-6** The skill shall direct agents to pass the questions that spec work raises to the engineer, rather than resolve them silently.
  - *Source:* NEED-2 · "Let's make sure the skill encourages #2 as well as #1."
- ✅ **AGENT-7** When the engineer asks why a requirement changed or disappeared, the agent shall answer with the reason recorded for that change.
  - *Source:* "say 'hey why does this component no longer have a requirement to do x or y' and the agent is able to explain". The recorded reason comes from CHANGE-5.
- ✅ **AGENT-8** When the engineer asks for stronger verification of a requirement, the agent shall add verification items for it.
  - *Source:* "I want more robust test coverage on this important invariant"
- ✅ **AGENT-9** When the engineer accepts a flagged failure, the agent shall update that verification item's expected result to the accepted behavior.
  - *Source:* "If the user says lgtm, then the doc expectations must be updated." See Q6.
- ✅ **AGENT-10** In spec-first mode, the agent shall implement the approved spec by working through the to-do list for the target implementation.
  - *Source:* "then the implementation is created, the REQs and VIs checked off one by one"
- ✅ **AGENT-11** When a spec-first change is complete, the agent shall list each difference between the approved spec and the final spec, or state that there are none.
  - *Source:* "'done, and I had to change a few things for you to review' or 'done, and everything was able to be made to spec'"
- 🟡 **AGENT-12** When the main agent tries to finish, a hook shall run the checker and return any findings to the agent.
  - *Why:* keeps AGENT-3 true even when the agent forgets, or doesn't have the skill loaded. A Claude Code Stop hook can block finishing and hand the findings back to the agent.
- 🟡 **AGENT-13** Each auditor shall be a fresh-context subagent that did not author the change it audits.
  - *Refines:* "it's important that the system engineers who make the requirements are not also the same ones that make the verification items"
  - *Why:* this adapts your independence rule. In code-first mode one agent writes the code, tests and spec, so independence has to come from review instead of from separate authors.
- 🟡 **AGENT-14** One auditor shall examine only the pre-existing tests and verification items that the change modified or deleted.
  - *Why:* new tests mostly add coverage. Edited and deleted tests are where weakening happens.
- 🟡 **AGENT-15** An auditor shall probe each new or changed critical requirement for ambiguity, by comparing how isolated agents read it.
  - *Why:* the scenario probe from our earlier discussion, applied only where it pays off.
- 🟡 **AGENT-16** For each critical requirement in a change, an auditor shall try to describe an implementation that passes the requirement's verification items yet violates it.
  - *Why:* if the auditor succeeds, the verification is too weak. This is a cheap, reasoning-based relative of mutation testing.
- 🟡 **AGENT-17** When a requested change contradicts an approved requirement, the agent shall raise the contradiction with the engineer before the change merges.
  - *Why:* this is the highest-value steering point. You learn that the request and the spec disagree while choosing between them is still cheap. See Q4.
