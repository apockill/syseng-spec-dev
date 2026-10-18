# Writing needs, requirements and verification items

## Layers

The spec reads top-down. The engineer reads the top two layers. The rest is for drilling in, and for agents.

- **Needs** are outcomes the engineer wants, in their own terms.
  - Draft them only from what the engineer says.
  - Record the context too: their reasoning, and any scenarios of use, paraphrased rather than quoted.
  - Nothing verifies needs. The engineer validates them.
- **System requirements** say what the system as a whole shall do. Each one `serves:` one or more needs.
- **Constraints** are limits the engineer puts on the solution, such as the implementation language.
- **System-element requirements** refine a system requirement for one part of the system. Each one `traces_to:` exactly one requirement, and never restates it.
  - A requirement that records a design choice rather than an ask is `derived: true`, with a `why`. Derived requirements are the first things the engineer should review.

System elements form a tree, one `parent` each, with the system at the root. Reuse goes in `depends_on`, never in a second parent. When an element changes, everything that depends on it is affected.

## Wording

The checker enforces these rules. Its errors explain each one, and references/rules.md has the details.

- **Exactly one "shall"** per requirement.
- **Shape:** `[condition, ]<subject> shall <response>.` Put conditions at the front (When, While, If, Where, In, During, At …).
- **No vague words** ("easy", "fast", "appropriate"). State something checkable instead.
- **No escape clauses** ("where possible", "as needed").
- **No open-ended lists** ("etc.") and no "and/or".
- **No "be able to".** Say what the subject does.
- **"each" or "every"**, not "any", "all" or "both".
- **No purpose clauses** ("so that …"). The reason goes in `why`.
- **No code names:** no identifiers, file names or call syntax. A rebuild in another language has to be able to follow the requirement.
- **No test wording.** How a requirement is checked belongs in a verification item.

Every requirement carries its rationale. Agent proposals use `why:`. The engineer's own words use `source:`, quoting them.

## Verification items

A verification item says how one or more requirements are checked:
- `method`: test, analysis, demonstration or inspection.
- `technique`: unit test, integration test, reasoning check or manual.
- `description`: written independently of language, so a port can rebuild the test.
- `tests`: links per implementation, for example `{python: [tests/test_x.py::test_y]}`.

System requirements also get system-level verification, such as an end-to-end run, not only their children's tests.

## Approvals

The engineer approves meaning: needs, requirements, verification items, decision records and element definitions. Each approval stores a fingerprint of the item's meaning.
- Rewording an item un-approves it.
- Re-linking an item's tests doesn't.

Links the checker can verify need no approval.
