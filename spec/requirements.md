# Requirements

*Round 3, 2026-10-11.* This is the spec for this toolkit, written as an exercise in the workflow it describes. It is one file so it can be reviewed in one sitting. Once the toolkit exists, it splits into per-component directories (MODEL-1).

- **What changed in round 3:** [changes/2026-10-11-round-3.md](changes/2026-10-11-round-3.md). Read that, not this whole file.
- **Vocabulary:** [glossary.md](glossary.md) (proposed; see Q18).

## How to read this

- ✅ **CONFIRMED**: states something you asked for. The quote under it is my source. Quotes are your words with typos fixed; "…" marks a cut and [brackets] a substitution.
- 🟡 **NEEDS REVIEW**: I added it, or I added substance to something you asked for (a number, a mechanism, a scope). *Why* gives my reasoning, and *Refines* names the ask it builds on. These are the places I'm steering, so these are the ones to read.

**88 confirmed · 54 need review · 5 open questions.**

## Open questions

8. **Who may write needs?** (MODEL-12) This was waiting on vocabulary, which [glossary.md](glossary.md) now proposes. A need is an outcome you want, judged by you (validation). A requirement is a checkable statement that agents verify. My lean: only you write needs, and agents propose them to you as questions.
12. **What gets approved individually?** (MODEL-25) Proposal: each spec item has its own approval. A spec item is any need, requirement, verification item or decision record, plus each component's own definition (its purpose, parent and dependencies). Test links and related-code lists are not approved; the checker polices those. In short, you approve meaning and the checker verifies the links to code.
16. **Restructure into layers before building?** Systems engineering writes system requirements that trace to the needs. It then allocates those to components, where they become component requirements (flow-down). Flow-down is the compression NEED-1 asks for: you'd read about 15 system requirements and look at components only where you care, instead of reading all 142 component-level items. Restructuring means three things:
    - (a) writing the system requirements;
    - (b) tracing every component requirement up to one of them;
    - (c) moving design choices (hooks, YAML on stdin, plugin packaging, fingerprints…) out of requirements and into decision records.

    My lean: yes, as the next round, before building.
17. **Add your CUJs as an item type?** Systems engineering calls them operational scenarios and writes them before needs. Ours exist only in chat, with NEED-6 and NEED-7 hinting at them. As items, they would ground the needs, give validation something concrete ("does CUJ 2 actually work?"), and become the first scenarios for agent-behavior evals (Q15). My lean: yes.
18. **Adopt systems-engineering vocabulary?** See [glossary.md](glossary.md), especially two choices:
    - Keep "component" (SE says "system element").
    - Replace "modality" with SE's four verification methods (Test, Analysis, Demonstration, Inspection), keeping unit test, integration test and reasoning check as the techniques under them.

    My lean: keep "component", and adopt the four methods.

### Resolved

| Q | Round | Resolution | Items |
|---|---|---|---|
| 1 | 2 | Agents edit the spec through the CLI, and a hook blocks direct edits. | CLI-1, CLI-5 to CLI-8, AGENT-20 |
| 2 | 3 | Expensive checks never run automatically, and the agent runs every cheap check after each change. | VERIFY-6, AGENT-30; VERIFY-7 and VERIFY-9 removed |
| 3 | 3 | Auditors run before your review. | AGENT-4 |
| 4 | 2–3 | Contradictions are always reported. Stopping to ask happens only in spec-first mode, and code-first never stops. | AGENT-17, AGENT-18, AGENT-28 |
| 5 | 2 | Reasoning checks run in fresh, non-forked subagents that read code but not the spec. | REASON-2, REASON-5 to REASON-7 |
| 6 | 2 | When an accepted failure contradicts a requirement, the requirement changes and you get the alternatives. | AGENT-19 |
| 7 | 2 | Approvals are fingerprinted records that the checker can verify. | MODEL-24 to MODEL-26, CHECK-14, CHECK-15 |
| 9 | 2 | "Expensive" covers time as well as tokens, and full runs happen on request. | MODEL-9, MODEL-23, VERIFY-11 to VERIFY-13, AGENT-22 |
| 10 | 2 | Code-first is the default mode. | CHANGE-9 |
| 11 | 3 | Where agents make changes is left to you and the harness. Quick changes come first when you ask. | AGENT-32, AGENT-29 |
| 13 | 3 | Chat approvals are allowed when unambiguous. | AGENT-21, AGENT-33, AGENT-34 |
| 14 | 3 | No transcript archive. Decisions live in paraphrased decision records on components. | MODEL-28, AGENT-24, AGENT-35; AGENT-26 removed |
| 15 | 3 | Shelved. The AGENT requirements are demonstrated in real use until there's an eval harness. | AGENT section note |

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
- ✅ **NEED-7** The engineer needs to develop quickly, running the full verification only occasionally and without supervising it.
  - *Source:* "I want to be able to develop quickly with agility, and occasionally say 'hey let's run the full suite' and walk away"
- ✅ **NEED-8** The engineer needs the reasoning behind each decision to stay available to future agents and to the engineer.
  - *Source:* "any documentation, links to external docs, things that came up in the building, build notes, reasoning for why something is the way it is, should be persisted"

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

A spec holds components, needs, requirements, verification items, decision records and implementations, plus the links and approvals between them.

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
- ✅ **MODEL-9** Each verification item shall have a cost tier: cheap, or expensive when it needs model calls, subagents or a long run time.
  - *Source:* "Expensive (e.g. not fully automated steps that require extra tokens/subagents spun up) should be a separate tier of tests" · "Expensive is not just a function of tokens, but time."
- ✅ **MODEL-10** Each component shall list its related code by path or pattern, with no limit on how many components a file relates to.
  - *Source:* "Should we decouple it, such that components can call out related code files" · "I'm not sure about 1 file to 1 component"
- ✅ **MODEL-24** The spec shall record each approval by the engineer together with a fingerprint of the approved content.
  - *Source:* "a list of properties stating when the file has been LGTMed by the user, including an 'approved' + some kind of git state of the file? Or like hash?"
- ✅ **MODEL-27** Each spec item and change record shall be able to link to its context: artifacts, documents, external links and build notes.
  - *Source:* "in the schema, we should have a way to link to context … any documentation, links to external docs, things that came up in the building, build notes". Links to conversation transcripts were dropped in round 3.
- ✅ **MODEL-28** Each component shall keep its decision records: a dated history of the decisions about it, each with its reasoning and the alternatives considered.
  - *Source:* "These are more like ADRs (architecture decision records) that are attached to components to show historical reasoning and changes over time."
- 🟡 **MODEL-11** Each component except the root shall name exactly one parent component, recorded separately from its dependencies.
  - *Why:* "is part of" (home feed → side panel) and "depends on" (side panel → image cache) are different relations. Requirements flow down the first, and change impact flows along the second. If the two are mixed, neither works.
- 🟡 **MODEL-12** The spec shall hold needs, meaning goals that can't be verified directly, as a third kind of item, each traced to the requirements that serve it.
  - *Why:* top-level goals such as NEED-1 can't be tested, and forcing them into "shall" form produces fake precision. This document already uses needs. See Q8.
- 🟡 **MODEL-13** Each requirement shall carry a rationale.
  - *Why:* the rationale is the first thing an agent reads when you ask why a requirement exists. That's why the NASA and INCOSE handbooks make it mandatory.
- 🟡 **MODEL-14** Each requirement shall record its origin: stated by the engineer, or proposed by an agent.
  - *Refines:* "we may want to consider adding this functionality to the rendering UI, so I know what to read"
  - *Why:* makes this document's ✅/🟡 split permanent. Approval (MODEL-24) tracks what you've seen; origin tracks whose idea it was.
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
- 🟡 **MODEL-23** A run time shall count as long when it exceeds 60 seconds, unless the repository's configuration sets another limit.
  - *Why:* keeps the cheap tier fast enough to run after every change. 60 seconds is a guess, which is why it's configurable.
- 🟡 **MODEL-25** Approvals shall apply to individual items (needs, requirements and verification items), not to whole files.
  - *Refines:* MODEL-24's source (you suggested per file).
  - *Why:* one reworded requirement shouldn't un-approve the others in its file. See Q12.
- 🟡 **MODEL-26** Each approval shall store the content it approved.
  - *Why:* a fingerprint shows *that* something changed. Only the stored content shows *what* changed (REVIEW-11).

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
- ✅ **CHECK-14** The checker shall report as unapproved each item that has no approval, or whose content no longer matches its approval's fingerprint.
  - *Source:* "Then the CLI can derive when the file is not approved (e.g. a subagent went and changed things, so now the hash doesn't match?)"
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
- 🟡 **CHECK-15** When preparing a merge, the checker shall report each unapproved item as a finding.
  - *Why:* keeps the main branch limited to what you've seen (NEED-1). Approving takes a click on the review page (REVIEW-13) or an explicit message in chat (AGENT-33).

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
- ✅ **VERIFY-6** The runner shall run expensive-tier items only when the engineer explicitly requests them.
  - *Source:* "I don't want it to spin up the reasoning agents every time automatically (a human should gate that)" · "occasionally say 'hey let's run the full suite'"
- ✅ **VERIFY-8** When an expensive-tier item fails, the runner shall add the failure to the change's list of decisions for the engineer.
  - *Source:* "If reasoning or integration+reasoning tests fail, the LLM should add it to a list of things to flag to the user."
- ✅ **VERIFY-11** When the engineer requests a full run, the runner shall run every verification item in every tier without needing the engineer present.
  - *Source:* "occasionally say 'hey let's run the full suite' and walk away"
- ✅ **VERIFY-12** At the end of a full run, the toolkit shall produce a summary of the product's health.
  - *Source:* "come back with … an AI summary of the health of the code"
- 🟡 **VERIFY-13** The health summary shall list each component's verification status, each change the run made with its reason, each unapproved item, and each requirement without verification.
  - *Why:* this is what you'd want to know on returning: what's broken, what agents changed while you were away, and what's waiting for you.
- *Removed in round 3:*
  - VERIFY-7 (merge-time scope of expensive items): expensive items now run only when you ask (VERIFY-6).
  - VERIFY-9 (run every cheap item at merge): replaced by AGENT-30, which runs them after every change.
  - VERIFY-10 (automatic reasoning check of tests against descriptions at merge): moved into the pre-review audits as AGENT-31.

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
- ✅ **REASON-2** The modality shall run each reasoning check in a fresh subagent that does not inherit the conversation, given only its item's prompt and declared inputs.
  - *Source:* "Subagents that do reasoning should be spun up with 0 context about the project, and only given what is absolutely necessary to verify … (this should be a req)" · "I imagine there's a 'forking' ability, which preserves user conversation. If that exists, I do not want to use it."
- ✅ **REASON-5** A reasoning check shall be able to read the product's code, except the spec directory.
  - *Source:* "For the subagent to verify and reason through things, it will need to read code. However, we should tell it to NOT read in spec/ directory."
- 🟡 **REASON-3** Each reasoning check shall return a pass or fail verdict with evidence quoted from its inputs.
  - *Why:* a bare verdict can't be audited. Quoted evidence shows you why it failed within seconds.
- 🟡 **REASON-4** For an item that verifies a critical requirement, the modality shall take the majority verdict of three independent runs.
  - *Refines:* "the goal being to have slightly more deterministic results"
  - *Why:* one sample from a nondeterministic judge tells you little, and three runs is the smallest number that gives a majority. Limiting this to critical requirements keeps the token cost down.
- 🟡 **REASON-6** A hook in the reasoning-check subagent's definition shall block reads of the spec directory.
  - *Why:* an instruction can be ignored, but a hook can't be. Claude Code lets a subagent definition carry its own hooks. It's a small hook: refuse reads under the spec directory and drop spec hits from search results. Your round-3 call: retract it if it turns out to be fiddly.
- 🟡 **REASON-7** The reasoning-check subagent's definition shall exclude the project's instruction files.
  - *Why:* fresh (non-fork) subagents still load CLAUDE.md and AGENTS.md by default, and those files can carry project context or spec-related instructions. The definition's `omitClaudeMd` setting turns that off.

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
- ✅ **CHANGE-9** When a request names no mode, the toolkit shall use code-first mode.
  - *Source:* your answer to Q10: "Agree".
- 🟡 **CHANGE-4** Each change record shall capture the engineer's request in the engineer's own words.
  - *Why:* lets auditors ask "you asked for X, so why does the spec now also say Y?" without a separate planning step.
- 🟡 **CHANGE-5** Each change record shall give a reason for each requirement the change added, modified or removed.
  - *Refines:* "I view the spec diff and say 'hey why does this component no longer have a requirement to do x or y' and the agent is able to explain"
  - *Why:* an agent starting from a fresh context months later can only answer "why?" if someone wrote the reason down at the time.
- 🟡 **CHANGE-8** Each change record shall name the implementation the change targets, defaulting to the primary implementation.
  - *Why:* CHECK-11 and the to-do list need to know which implementation "done" refers to. For a port, it's the new implementation.
- *Removed in round 2:*
  - CHANGE-6 (store the approved spec revision): replaced by MODEL-26.
  - CHANGE-7 (merging counts as approval): replaced by approval records (MODEL-24).

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
- ✅ **REVIEW-13** The review page shall let the engineer approve items or give feedback on them.
  - *Source:* "click 'approve' (or give feedback)"
- 🟡 **REVIEW-8** The renderer shall mark each unapproved item.
  - *Refines:* "we may want to consider adding this functionality to the rendering UI, so I know what to read"
  - *Why:* "unapproved" (CHECK-14) means exactly "what you haven't seen yet". That's what this document's 🟡 tags approximate by hand.
- 🟡 **REVIEW-9** In a diff, the renderer shall highlight in amber each verification item that changed while the requirements it verifies did not.
  - *Why:* that's where test weakening hides. In a 2025 benchmark, Claude models cheated mostly by editing test files, so this case deserves its own color.
- 🟡 **REVIEW-10** In a diff, the renderer shall show the recorded reason beside each changed or removed requirement.
  - *Why:* answers most "why?" questions before you need to ask them.
- 🟡 **REVIEW-11** The renderer shall show each unapproved item's differences from its last approved content.
  - *Why:* one mechanism covers both the spec-first "I had to change a few things" case and every other change since your last approval.
- 🟡 **REVIEW-12** In a diff, the renderer shall show the decisions for the engineer above all requirement changes.
  - *Why:* those decisions are the steering points (NEED-2), so they shouldn't be buried at the bottom.

## CLI: the command-line tool

The single tool through which agents, and the engineer, query, edit, check, verify and render the spec.

- ✅ **CLI-1** The toolkit shall provide one command-line tool through which agents query, edit, check, verify and render the spec.
  - *Source:* "The commandline interface the LLM uses" · "I want the CLI to be the main way agents edit the spec."
- ✅ **CLI-2** The CLI shall generate, for a named implementation, a to-do list of the requirements and verification items not yet implemented or not passing in it.
  - *Source:* "This ends up forming an automated 'todo' list for the LLM … 'let's implement this project in rust' and the todo list can be regenerated but for an entire different implementation"
- ✅ **CLI-5** Before applying an edit, the CLI shall show the agent the edit's context: affected parent and child requirements, linked verification items and tests, dependent components, and approval status.
  - *Source:* "if an agent wants to edit the spec, the CLI has a chance to intercept the request and give extra context (for example, dumping the descendant V&V / REQs into context, then asking 'confirm?' or something)"
- 🟡 **CLI-3** The CLI shall answer four queries: one component's spec, the components related to given files, the trace from a requirement to its verification items and tests, and a requirement's history (its rationale, each change with its reason, and its linked context).
  - *Why:* lets an agent pull exactly the spec it needs into context, instead of all of it. The history query is how a later agent learns why a requirement is the way it is (AGENT-25).
- 🟡 **CLI-4** The CLI shall order a to-do list so that each component's items follow those of the components it depends on.
  - *Why:* lets an agent build from the bottom up. A port starts at the leaf components and works upward.
- 🟡 **CLI-6** When an edit affects approved items or items that others depend on, the CLI shall apply it only after the agent acknowledges each affected item by name.
  - *Refines:* "then asking 'confirm?'"
  - *Why:* a model will rubber-stamp a generic "confirm?". Naming each affected item with a one-line note makes the agent actually consider it, and those notes become reasons you can read. Edits that affect nothing apply immediately, so friction only appears where there's something to consider.
- 🟡 **CLI-7** The CLI shall accept a batch of edits as one YAML document on standard input.
  - *Why:* multi-line prose passed as shell arguments breaks on quotes, and a heredoc doesn't. One call can also carry a twenty-requirement update.
- 🟡 **CLI-8** The CLI shall reject a modification or removal that has no reason.
  - *Why:* enforces CHANGE-5 at write time, while the reason is fresh.

## AGENT: skills, subagents and hooks

These fit the methodology into an agent's normal coding work.

*Verification of the AGENT requirements is deferred (Q15, round 3). They're demonstrated in real use until there's an eval harness, and the first eval scenarios should come from real failures.*

- ✅ **AGENT-1** In code-first mode, the skill shall let the main agent edit code without first reading the spec.
  - *Source:* "it spends time looking at code, and WHEN IT ADDS VALUE also reading the current REQs and V&V, but otherwise … it probably doesn't need to"
- ✅ **AGENT-2** The skill shall direct the main agent to update the requirements and verification items a change affects, as part of that change.
  - *Source:* "It makes all the changes and tries its best to update V&V along the way."
- ✅ **AGENT-3** The main agent shall report a change as done only after the checker reports no findings for it.
  - *Source:* "At the end, it runs the linter and is told 'hey XYZ tests have been added and are not associated with VERs …'"
- ✅ **AGENT-4** Skeptical auditor subagents shall review each change's spec updates before the engineer reviews the change.
  - *Source:* "have skeptical subagents run audits too, to ensure everything is up to date. Then I go in, read the specs" · Q3: "Before review sounds fine."
- ✅ **AGENT-5** The toolkit shall critique each new or changed requirement and verification item.
  - *Source:* "How do we write some way to critique whether or not a requirement is well written or whether or not a verification item is well written"
- ✅ **AGENT-6** The skill shall direct agents to pass the questions that spec work raises to the engineer, rather than resolve them silently.
  - *Source:* NEED-2 · "Let's make sure the skill encourages #2 as well as #1."
- ✅ **AGENT-7** When the engineer asks why a requirement changed or disappeared, the agent shall answer with the reason recorded for that change.
  - *Source:* "say 'hey why does this component no longer have a requirement to do x or y' and the agent is able to explain". The recorded reason comes from CHANGE-5.
- ✅ **AGENT-8** When the engineer asks for stronger verification of a requirement, the agent shall add verification items for it.
  - *Source:* "I want more robust test coverage on this important invariant"
- ✅ **AGENT-9** When the engineer accepts a flagged failure, the agent shall update that verification item's expected result to the accepted behavior.
  - *Source:* "If the user says lgtm, then the doc expectations must be updated."
- ✅ **AGENT-10** In spec-first mode, the agent shall implement the approved spec by working through the to-do list for the target implementation.
  - *Source:* "then the implementation is created, the REQs and VIs checked off one by one"
- ✅ **AGENT-11** When a spec-first change is complete, the agent shall list each difference between the approved spec and the final spec, or state that there are none.
  - *Source:* "'done, and I had to change a few things for you to review' or 'done, and everything was able to be made to spec'"
- ✅ **AGENT-17** The agent shall report every contradiction between a request and an approved requirement.
  - *Source:* "always _mention_ 'hey, this breaks X, Y, changes Z'"
- ✅ **AGENT-18** In spec-first mode, when a contradiction is one the engineer would likely want to decide before more work is done, the agent shall stop and ask before continuing.
  - *Source:* "but not let that halt execution UNLESS X or Y is deemed by the LLM to likely be something the user would want to have an opinion on / confirmation on" · round 3: "Only in cases where the user is trying to plan a change should we have things that halt the flow and come back and ask the user what to do."
- ✅ **AGENT-19** When accepting a flagged failure requires changing a requirement, the agent shall change it and add a decision for the engineer listing the alternatives.
  - *Source:* "I think yes, and with a flag to the user for these cases- like, 'hey, because of X or Y we needed to change the REQ. The alternatives are A B or C'"
- ✅ **AGENT-21** Only the engineer's own actions shall create approvals: the review page, the engineer's terminal, or an explicit approval in chat.
  - *Source:* "Yeah I think LGTM in chat is fine, with the caveat that there can be no ambiguity to what I mean" · "e.g. a subagent went and changed things, so now the hash doesn't match"
- ✅ **AGENT-22** During a full run, agents shall attempt to fix each failure, by changing code, requirements or verification items.
  - *Source:* "come back with maybe some code changed, some reworded reqs, some updated / new VIs". Their changes stay unapproved until you approve them (CHECK-14).
- ✅ **AGENT-23** When a decision is made in conversation, the agent shall persist its reasoning and sources as context linked from the affected items.
  - *Source:* "if I'm designing and debating with an agent, and an Artifact is made with some visualizations, and I say 'yeah that looks cool lets do that'- then the implementation happens, reqs are made / updated, I'd like the agent to persist that"
- ✅ **AGENT-24** The agent shall write a decision record for each decision made while building, attached to each component the decision affects.
  - *Source:* "These are more like ADRs (architecture decision records) that are attached to components to show historical reasoning and changes over time."
- ✅ **AGENT-25** Before modifying or removing an approved requirement, the agent shall read its rationale and linked context.
  - *Source:* "an implementing agent might say 'hmm, can I change this REQ? Let me read up on why they made it the way they made it...'"
- ✅ **AGENT-28** In code-first mode, the agent shall finish the requested change without stopping to ask the engineer.
  - *Source:* "it must remain possible to have a CUJ where the user can state what they want, say 'go for it', and come back to the changes having been made, and read the spec"
- ✅ **AGENT-29** When the engineer asks for a quick change, the agent shall tell the engineer as soon as the change is usable, before finishing its tests and spec updates.
  - *Source:* "sometimes I just want an agent to make a damn change quick, so I can run my binary and play with it while other changes get done … Sometimes I want the change done first, then it can spend all day polishing"
- ✅ **AGENT-30** The agent shall run every cheap-tier item before reporting a change as done.
  - *Source:* "I fully expect the agent to run all unit tests after changes anyways- its a single command."
- ✅ **AGENT-32** The skills shall leave the choice of where agents make changes (working tree, branch or worktree) to the engineer and the agent harness.
  - *Source:* "Let's not encode this in the skill. Agent harnesses are getting better and better, I don't want to be overly prescriptive."
- ✅ **AGENT-33** A chat message shall count as an approval only when it states unambiguously which items it approves.
  - *Source:* "agents say 1000 things in one chat, if I say lgtm I might mean 'yeah sure' to some of them, not 'yes, and also approve every req'"
- ✅ **AGENT-35** A decision record shall present the engineer's reasoning as paraphrase, never as a direct quote.
  - *Source:* "Don't directly quote, maybe clean it up a bit. Be careful not to imply its a direct quote."
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
- 🟡 **AGENT-20** A hook shall block agents' direct edits to spec files, naming the CLI command to use instead.
  - *Why:* agents default to editing files. A refusal that names the alternative redirects them reliably, and it keeps every edit going through CLI-5's context step.
- 🟡 **AGENT-31** An auditor shall compare each changed verification item's tests against its description.
  - *Why:* this was VERIFY-10. Running it automatically at merge would spin up reasoning agents without your say-so. The pre-review audits are where you accepted automatic reasoning work (Q3).
- 🟡 **AGENT-34** A hook reading the engineer's own message shall record each chat approval, applying it only to the items as they were last shown to the engineer.
  - *Why:* the agent never records an approval itself, so it can't act on a misreading. An approval also can't cover anything that changed after you looked.
- *Removed:*
  - AGENT-26 (archive transcripts), in round 3: decision records replace it (MODEL-28, AGENT-24).
