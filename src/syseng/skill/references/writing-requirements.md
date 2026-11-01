# Writing needs, requirements and verification items

## Layers

The spec reads top-down. The engineer reads the top two layers. The rest is for drilling in, and for agents.

- **Needs** are outcomes the engineer wants, in their own terms.
  - Draft them only from what the engineer says, with their intent on each.
  - Record the context too: their reasoning, and any scenarios of use, paraphrased.
  - Nothing verifies needs. The engineer validates them.
- **System requirements** say what the system as a whole shall do. Each one `serves:` one or more needs.
- **Constraints** are limits the engineer puts on the solution, such as the implementation language.
- **System-element requirements** refine a requirement of their element's parent; an element directly under the system refines a system requirement. Each one `traces_to:` exactly one requirement, and never restates it. If the parent has nothing to refine, give the parent a requirement of its own first.

System elements form a tree, one `parent` each, with the system at the root. Reuse goes in `depends_on`, never in a second parent. When an element changes, everything that depends on it is affected.

Place each requirement where the system's structure puts it, not where the engineer's request started. "Make a 3D game where the player's feet are purple" yields high-level requirements near the top and one detail deep in the tree (world → characters → player → model → textures). Each carries the intent its request expressed, and the detail sits under the textures.

## How deep

SKILL.md's rules, and references/requirement-depth.md for the rest: depth follows the engineer's intent, one requirement per noticeable feature, exact values only where stated, safety-critical or read by a named consumer.

## Wording

The checker enforces these rules, and each of its errors explains the rule it broke.

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

Every requirement carries its rationale: the person's intent, or the agent's `why:`.

## Intent records

What a person says goes on the items it directly expresses as intent records, through `spec edit`. Not every requirement has one: most follow from a few statements, and are derived.

```yaml
intent:
  - by: Ada Lovelace <ada@example.com>   # filled in from `git config syseng.author` when left out
    when: 2026-10-17 21:26                # filled in with the time of the edit when left out
    context: Discussing where detailed requirements belong.
    said: Wants the purple-feet detail placed deep in the tree, under the player model's textures, not near the top.
    basis: stated                         # or guided
    fingerprint: 3f2a9c0b71de             # always filled in by `spec edit`
```

- `said` summarizes, close to their words but never word for word, and in the third person. Keep their hedges and strength (probably, must), add no number or mechanism they didn't give, and say what they left open when they said so. No double quotation marks.
- `context` frames the statement: what was being discussed and what prompted it. It adds no claim of its own.
- `basis` is `stated` when what they said, taken alone, says what the item requires, and `guided` when their choice or constraint fixed it without saying it. When unsure, the lower level.
- An item no person addressed says where it came from instead: `basis: derived` (something above needs it) or `basis: added` (an agent's own idea).

## Verification items

A verification item says how one or more requirements are checked:
- `method`: test, analysis, demonstration or inspection.
- `technique`: unit test, integration test, reasoning check or manual.
- `description`: written independently of language, so a port can rebuild the test.
- `tests`: links per implementation, for example `{python: [tests/test_x.py::test_y]}`.

System requirements also get system-level verification, such as an end-to-end run, not only their children's tests.

## Linking tests

Every test links to a verification item: a test exists to protect a contract, so the spec should say which one. `spec check --todo` lists the tests nothing links, and `spec results status` does for every language.

Link first, add last:
1. **Find the requirement the test supports** and link it from that requirement's verification item. One item can link many tests, or a whole file, so a detailed test of an internal helper goes under the behaviour it serves.
2. **If nothing fits but people rely on the behaviour,** the spec is missing a contract: add the requirement (`basis: derived`), or a constraint for a rule of the project.
3. **Never add a requirement just to give a test a home.** Requirements follow the depth rules whether or not a test exists. Implementation details stay out, or the spec starts describing the code.
4. **If you can't say what contract a test protects,** raise it with the engineer: it may need strengthening, or it may not be needed.

## Levels and locks

Each item has a level of intent, computed every time and never stored:
- **explicit:** a person locked it. A lock is a person's own act, naming the items: a lock line in chat, a menu choice, the terminal, or the review page. Each lock records who, how, when, how many items were locked together, and the content's fingerprint. Every lock is kept, oldest first.
- **stated** or **guided:** from the item's intent records.
- **derived** or **added:** from its basis. A derived item under an added one counts as added.

An item keeps its level after it changes, until a person answers the change: a newer lock or intent record that matches it, or a rollback. Rewording an item changes its fingerprint; re-linking its tests doesn't. Links the checker can verify need no lock.
