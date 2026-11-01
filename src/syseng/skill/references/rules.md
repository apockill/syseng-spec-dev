# Checker rules

Every error the checker reports links here. Each rule says what it checks, why it exists and how to fix a finding.

The wording rules (W…) come from INCOSE's *Guide to Writing Requirements*, cited by rule number. The guide isn't freely available, so this page explains each rule on its own terms. The wording rules were tuned against this repository's own spec before they shipped.

Errors fail `spec check`. To-dos are listed by `spec check --todo` but don't fail it.

The wording rules (W…) flag patterns that are usually wrong. When one doesn't apply to an item, because you know why the rule exists and this case is the exception, allow it on that item with the reason: `allow: [{rule: W011, why: "the requirement is about how the product writes pronouns"}]`. The reason is reviewed like any other text.

## Contents

- Structure: S001, S002, S003, S004, S005, S006, S007, S008
- Traceability: T001, T002, T003, T004, T005
- Attributes: A001, A002, A003, A004, A005, A006, A007, A008, A009, A010, F001
- Conflicts: C001
- Verification items: V001
- Rendered views: V002, V003, V004, R001
- Wording: W001, W002, W003, W004, W005, W006, W007, W008, W009, W010, W011

## Structure

<a id="s001"></a>
### S001: unreadable or malformed spec file
The YAML didn't parse, or a file has the wrong shape. Item files must be lists of mappings with an `id`; `element.yaml` and `toolkit.yaml` must be mappings. Nothing else in a broken file was checked, so fix this first.

<a id="s002"></a>
### S002: duplicate ID
Two items share one ID, which makes traces, approvals and history ambiguous. Give the newer item the next unused number for its system element.

<a id="s003"></a>
### S003: retired ID reused
`retired.yaml` lists IDs that were removed. Old change records still refer to them, so reusing one would silently rewrite history. Pick a fresh number.

<a id="s004"></a>
### S004: nested system element
System elements live in one flat directory, `spec/elements/<ID>/`. The hierarchy is expressed by `parent:`, not by folders.

<a id="s005"></a>
### S005: broken decomposition tree
Requirements flow down `parent` links, so the links must form one tree: exactly one root (the system), every other element with exactly one existing parent, and no loops. Reuse belongs in `depends_on`, never in a second parent.

<a id="s006"></a>
### S006: broken dependency graph
`depends_on` drives change impact: when an element changes, everything that depends on it is affected. It must name real elements and contain no cycles. To break a cycle, extract the shared part into its own element that both sides depend on.

<a id="s007"></a>
### S007: missing or invalid field
A required field is missing or has a value the toolkit doesn't know. The message names the field.

<a id="s008"></a>
### S008: item in the wrong system element
An item lives in the directory its ID names: `CORE-3` in `elements/CORE/`, needs and system requirements in the system's directory, and a decision record with the first element it lists.

## Traceability

<a id="t001"></a>
### T001: broken trace
Every requirement answers "why do I exist?" by pointing upward:
- An element requirement points to one requirement with `traces_to`.
- A system requirement points to the needs it `serves`.

A requirement that records a design choice rather than an ask can set `derived: true`, but it must say `why`. Derived requirements are the first thing the engineer should review.

<a id="t002"></a>
### T002: need served by nothing
No system requirement serves this need, so nothing will ever meet it. Add one, or ask the engineer whether the need still stands. It's a to-do rather than an error, because needs can be recorded before the requirements that serve them, as spec-first planning does.

<a id="t003"></a>
### T003: dangling reference
A decision record, approval or verification item points at an ID that doesn't exist or isn't the right kind. Fix the ID or drop the reference.

<a id="t004"></a>
### T004: requirement without verification (to-do)
The requirement has no verification item yet. This is listed as a to-do, not an error. For requirements a change touches, the done gate will make it one.

On an element with sub-elements, a requirement that no sub-element's requirement refines is called out as neither decomposed nor verified: give it a verification item at its own level, or requirements below that refine it.

<a id="t005"></a>
### T005: requirement skips a level of the system breakdown (to-do, or error where enforced)
Requirements flow down the system breakdown. A requirement on an element refines one of its parent element's requirements; an element directly under the system refines a system requirement. The requirement tree then has the same shape as the element tree, and a detail such as "the player's feet are purple" sits under textures, under the player model, under characters, not near the top.
- Point `traces_to` at a requirement of the element's parent.
- If the parent has nothing that fits, give the parent a requirement of its own for this one to refine. Don't restate the parent's requirement.

It's a to-do until `flow_down: enforced` is set in spec/toolkit.yaml, which new repositories start with. Then it's an error.

## Attributes

<a id="a001"></a>
### A001: requirement without rationale
The rationale is what an agent reads first when someone asks why a requirement exists:
- If the requirement is the engineer's own words, set `source` to the quote.
- If an agent proposed it, set `why` to the reasoning.

<a id="a002"></a>
### A002: no intent and no basis
Every item says how directly a person asked for it. A person's words go on it as `intent:` records; an item no person asked for says where it came from with `basis: derived` (something above needs it) or `basis: added` (an agent's own idea). Verification items count as derived. In a spec not yet migrated, `origin: engineer` or `origin: agent` still counts.

<a id="a003"></a>
### A003: changed since a person locked, stated or guided it (to-do)
A person locked this item, asked for it, or shaped it, and its content has changed since their newest record. The item keeps its level until they answer: they keep it as it is now (a new lock or intent record), or it goes back to what they gave.

Every item has a level of intent, computed each time:
- **explicit:** a person locked it by name;
- **stated:** a person asked for it, and what they said, taken alone, says what it requires;
- **guided:** a person's choice or constraint fixed it without saying it;
- **derived:** something above it needs it, and no person addressed it;
- **added:** an agent added it unasked, and nothing a person gave needs it.

Derived and added items are the agent's to change. They aren't to-dos.

<a id="a004"></a>
### A004: alteration awaiting the engineer's answer (to-do)
A change altered an item the engineer approved, wrote or decided, and they haven't yet kept the alteration or had it rolled back. Ask them, giving the line that keeps it, such as `CHECK-3 LGTM`. The merge check lists these before a branch lands, and never fails because of them.

<a id="a005"></a>
### A005: lock for an unknown item
An approval names an item that doesn't exist. Remove it, or fix the ID.

<a id="a006"></a>
### A006: incomplete intent record
An intent record says what a person asked for, as a summary on the item it shapes. Each record needs:
- `by`: the person, as `Name <email>`;
- `when`: the date and time they said it;
- `context`: what was being discussed and what prompted it, adding no claim they didn't make;
- `said`: what they said, summarized close to their words;
- `basis`: `stated` when what they said, taken alone, says what the item requires, or `guided` when their choice or constraint fixed it. When unsure, use the lower level;
- `fingerprint`: the item's content when the record was made.

Add intent with `spec edit` (`intent:` on an add or modify). It fills in `by`, `when` and `fingerprint`.

<a id="a007"></a>
### A007: verbatim quote in an intent record
Intent records summarize. They keep the person's hedges and strength ("probably", "must"), add no number or mechanism they didn't give, and say what they left open when they said so. They never quote word for word, so conversation stays out of what the repository publishes. Double quotation marks are taken as the sign of a quote; single quotes and apostrophes are fine.

<a id="a008"></a>
### A008: invalid basis
An item no person stated, guided or locked says where it came from: `basis: derived` when something above it needs it, or `basis: added` when an agent added it on its own initiative. Added items are the most freely changed in a refactor, and the review page lists them for a person to keep or cut.

<a id="a009"></a>
### A009: field of the older format
After `spec migrate`, a spec keeps a person's words only as intent records: summarized, attributed, never quoted. Older fields are gone:
- `source`, `quotes` and `refines` become `intent:` records;
- `origin: engineer` becomes intent, and `origin: agent` becomes `basis: derived` or `basis: added`;
- the `derived` mark is retired, because every requirement traces to its parent's;
- locks hold no `words`, only a summary an agent adds, and their time is `locked_at`.

<a id="a010"></a>
### A010: invalid lock
A lock records who locked which content, how and when: `id`, `fingerprint`, `locked_at`, `by` (as `Name <email>`), `via` (terminal, chat, menu, page or restated), and optionally `batch`, `said` (a summary an agent adds), `note`, `after`, `text` and `migrated_from`. `spec lock` writes every field; fix the one the message names.

<a id="f001"></a>
### F001: feedback not yet answered
A person sent feedback from the review page, and one of its comments, corrections or roll-back requests has no response in the open change. Do what it asks, or explain why not, then record it with `spec feedback respond F<n> "..."`. Their next review page shows each comment with its response.

## Conflicts

<a id="c001"></a>
### C001: altered intent with no conflict raised
This change altered an item a person locked or stated, and nothing brings that to them. In code-first mode the change goes ahead, so the end of the change is where it's raised:
- `spec decide` with `kind: conflict`, `involves:` naming the item, and options, such as keeping the new text, rolling back, or rewording, with one recommended and each showing the text it would give;
- or, when the meaning didn't change, mark the edit `rewording: true`;
- or, when the person asked for this very change, add their request to the edit as `intent:` with basis stated.

In spec-first mode, `spec edit` refuses such an edit until the person has chosen an option, and the edit names it with `conflict: D<n>`.

## Verification items

<a id="v001"></a>
### V001: invalid verification item
A verification item needs:
- `verifies`: the requirements it checks;
- a `method`: test, analysis, demonstration or inspection;
- a `technique`: unit test, integration test, reasoning check or manual;
- a language-independent `description`.

## Rendered views

<a id="v002"></a>
### V002: linked test not found
A verification item links a test that doesn't exist: the file is missing, or the file has no test by that name. A link is `path` or `path::name`, resolved against the implementation's root. In a Python file the name is a pytest test (`test_x`, or `TestThing::test_x`, with any `[parameters]` ignored). In a C++ file it's a GoogleTest (`Suite.Test`, declared with `TEST`, `TEST_F`, `TEST_P` or `TYPED_TEST`). In any other file, the name only has to appear in it. Fix the link, or remove it if the test is gone.

<a id="v003"></a>
### V003: test no verification item links (to-do)
A Python test in the implementation's tree that no verification item links, listed per file. It checks something the spec doesn't claim, or a requirement that's missing. See "Linking tests" in references/writing-requirements.md. Link it from the verification item whose requirement it checks, or add the requirement it shows is missing. Folders that are hidden, vendored (`node_modules`, `site-packages`) or hold app data (`state`) are skipped.

<a id="v004"></a>
### V004: roll-up over an unverified child
A verification item with technique `roll-up` verifies a requirement through the verification of the requirements that refine it, the way systems engineering verifies a higher-level requirement by analysis of its subordinate results. It holds only while every child is verified: verify the child, or verify the parent at its own level. Prefer a test at the parent's own level where one wouldn't be arbitrary.

<a id="r001"></a>
### R001: stale Markdown view
The review page replaced the generated Markdown views. A `requirements.md`, `decisions.md` or change-record `.md` left in spec/ shows a spec that no longer exists. `spec render` removes it; `spec review` writes the page.

## Wording

The wording rules apply to requirement text: system requirements, constraints and element requirements. Text inside double quotes is a mention, not part of the sentence, so a quoted "shall" doesn't count.

<a id="w001"></a>
### W001: not exactly one "shall" (INCOSE R18, R19)
One requirement, one obligation. A second "shall" hides a second requirement that can't be traced, verified or approved on its own. With no "shall", the sentence states a fact, not an obligation.

- ✗ The checker shall run the rules and shall print a summary.
- ✓ The checker shall run every rule. / The checker shall print a summary after each run.

<a id="w002"></a>
### W002: sentence shape (EARS; INCOSE R1, R2)
A requirement names who shall do what: `[condition, ]<subject> shall <response>.` Conditions go up front: When, While, If, Where, In, During, At and similar, and several may be chained. With no subject before "shall", nobody owns the obligation.

- ✗ Shall report findings.
- ✓ When an agent finishes a change, the checker shall report its findings.

<a id="w003"></a>
### W003: escape clause (INCOSE R8)
"Where possible", "as needed" and "if necessary" let any implementation claim compliance, so the requirement can never fail. Delete the escape, or state the exact condition.

- ✗ The checker shall finish in 5 seconds where possible.
- ✓ The checker shall finish within 5 seconds on a 100,000-line repository.

<a id="w004"></a>
### W004: open-ended wording (INCOSE R9, R15)
"etc." leaves the reader to guess the rest of the list, and "and/or" leaves them to guess the logic. Name every member, or split "and/or" into explicit cases.

<a id="w005"></a>
### W005: vague term (INCOSE R7)
"Easy", "fast", "appropriate" and "robust" can't be measured, so two readers will disagree on whether the requirement holds. Replace the word with a number, a named condition or an observable behavior.

- ✗ …wherever those make the engineer's interaction easier.
- ✓ …wherever those let the engineer answer or review in fewer steps.

These are exempt: "how many" (a quantity, not a vague amount), and capitalized words inside a proper name, such as "Easy Approach to Requirements Syntax".

<a id="w006"></a>
### W006: superfluous infinitive (INCOSE R10)
"Shall be able to X" describes a capability, and something that never actually does X still satisfies it. Say what the subject does.

- ✗ The engineer shall be able to accept a set of recommendations in one statement.
- ✓ The toolkit shall accept the recommended options of a set of open decisions from one statement by the engineer.

<a id="w007"></a>
### W007: universal quantifier (INCOSE R32)
"Any", "all" and "both" blur whether the requirement applies to each case or to the set. Use "each" or "every", or name the set. "Both … and" joining two phrases is a conjunction, not a quantifier, so it's exempt.

<a id="w008"></a>
### W008: purpose clause (INCOSE R20)
"In order to" and "so that" add a second claim, the purpose, which nothing verifies. Reasons belong in `why`.

<a id="w009"></a>
### W009: language-specific name (INCOSE R31)
Requirements describe behavior in terms any implementation can meet, so a Rust rebuild can follow them. Code spans, file names, snake_case or camelCase identifiers and call syntax belong in test links and related-code lists. An exact value another program depends on (a JSON field name, a file name in a format others read) is part of the requirement: put it in double quotes, and the check reads it as a quoted value.

<a id="w010"></a>
### W010: requirement states its own test (INCOSE R31)
A requirement says what must hold. How it's checked belongs in a verification item, written separately, so that verification stays independent.

- ✗ The checker shall be verified by a unit test that…
- ✓ The checker shall report each duplicate ID. *(The unit test lives in a verification item.)*

<a id="w011"></a>
### W011: gendered pronoun
A need, a requirement or an intent record uses he, him, his, she, her or hers. Agents guess pronouns from names, and a wrong guess misgenders a real person in a record that lasts. Name the person or their role ("the engineer", "the operator") instead. Checked in needs, requirements, and the `said` and `context` of every intent record.
