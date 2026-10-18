# Checker rules

Every error the checker reports links here. Each rule says what it checks, why it exists and how to fix a finding.

The wording rules (W…) come from INCOSE's *Guide to Writing Requirements*, cited by rule number. The guide isn't freely available, so this page explains each rule on its own terms. The wording rules were tuned against this repository's own spec before they shipped.

Errors fail `spec check`. To-dos are listed by `spec check --todo` but don't fail it.

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

## Attributes

<a id="a001"></a>
### A001: requirement without rationale
The rationale is what an agent reads first when someone asks why a requirement exists:
- If the requirement is the engineer's own words, set `source` to the quote.
- If an agent proposed it, set `why` to the reasoning.

<a id="a002"></a>
### A002: missing origin
`origin` says whose idea an item is: `engineer` (from their words) or `agent` (a proposal). The review page uses it to show the engineer what to read.

<a id="a003"></a>
### A003: unreviewed item (to-do)
Nothing covers this item: neither it nor anything above it in the trace graph is approved, or it changed after the engineer approved it. An item under an approved item is delegated, and isn't a to-do. Approvals are recorded by `spec approve`, only from the engineer's own words.

<a id="a004"></a>
### A004: alteration awaiting the engineer's answer (to-do)
A change altered an item the engineer approved, wrote or decided, and they haven't yet kept the alteration or had it rolled back. Ask them, giving the line that keeps it, such as `CHECK-3 LGTM`. The merge check lists these before a branch lands, and never fails because of them.

<a id="a005"></a>
### A005: approval for an unknown item
An approval names an item that doesn't exist. Remove it, or fix the ID.

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

<a id="r001"></a>
### R001: rendered view out of date
`requirements.md` and `decisions.md` are generated. A stale view shows the engineer a spec that no longer exists. Run `spec render`, and never edit the views by hand.

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
Requirements describe behavior in terms any implementation can meet, so a Rust rebuild can follow them. Code spans, file names, snake_case or camelCase identifiers and call syntax belong in test links and related-code lists.

<a id="w010"></a>
### W010: requirement states its own test (INCOSE R31)
A requirement says what must hold. How it's checked belongs in a verification item, written separately, so that verification stays independent.

- ✗ The checker shall be verified by a unit test that…
- ✓ The checker shall report each duplicate ID. *(The unit test lives in a verification item.)*
