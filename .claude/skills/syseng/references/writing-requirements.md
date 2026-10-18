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

Place each requirement where the system's structure puts it, not where the engineer's request started. "Make a 3D game where the player's feet are purple" yields high-level requirements near the top and one detail deep in the tree (world → characters → player → model → textures), each quoting the words it expresses.

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

Every requirement carries its rationale. Agent proposals use `why:`. The engineer's own words go in `quotes:`.

## The engineer's words

Quote the engineer on each requirement their words directly express. Not every requirement needs a quote: most are derived from a few statements.

```yaml
quotes:
  - said: 2026-10-17 21:26        # when they said it
    words: |-                     # exactly what they wrote, typos and all; their reasoning, not just "yes"
      Like, the "players feet must be purple" shouldn't be close to the top of the tree.
    context: Discussing where detailed requirements belong.   # what was being discussed, and nothing more
```

The context line frames the quote. It never adds claims of its own. Older items keep the engineer's words in `source:`.

## Verification items

A verification item says how one or more requirements are checked:
- `method`: test, analysis, demonstration or inspection.
- `technique`: unit test, integration test, reasoning check or manual.
- `description`: written independently of language, so a port can rebuild the test.
- `tests`: links per implementation, for example `{python: [tests/test_x.py::test_y]}`.

System requirements also get system-level verification, such as an end-to-end run, not only their children's tests.

## Approvals

The engineer approves meaning: needs, requirements, verification items, decision records and element definitions. Each approval records who gave it, how (chat, a menu, the terminal, the review page, or a restatement), when, how many items were approved together, the engineer's words, and the decisions settled before it. Every approval is kept, oldest first.

Each item has a review state, computed every time and never stored:
- **approved:** the engineer approved this exact content;
- **changed:** they approved an earlier version, and it has changed since;
- **delegated:** not approved itself, but under an item that is approved. It's yours to decide while that item still holds;
- **unreviewed:** nothing above it is approved.

Rewording an item changes its state. Re-linking its tests doesn't. Links the checker can verify need no approval.
