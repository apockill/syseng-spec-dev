---
name: syseng
description: Systems-engineering spec workflow for repositories that have a spec/ directory with spec/toolkit.yaml. Use it for every change to such a repository, whether you're writing code first or the spec first. Also use it when the engineer asks why something is the way it is, says what they want, locks spec items, wants a feature planned before it's built, or wants an existing project brought into the method.
---

# Working with a systems-engineering spec

The engineer steers this project by reading its requirements, not its code. The spec records how directly a person asked for each item, so you can build fast and still know what you may reshape freely and what you must bring back to a person. Your job: keep the spec true to the code and the code true to the spec, and bring the engineer only what needs their judgment, most consequential first.

Run the toolkit as `spec` from the repository root. `spec <command> --help` explains each command, and its errors say what's wrong and how to fix it. If it reports that the toolkit isn't set up on this machine, tell the engineer.

## Read only what your task needs

| Your task | Read | Size |
|---|---|---|
| Any change to a repository that has a spec | this file | 100 lines |
| Bringing an existing project in | [references/onboarding.md](references/onboarding.md) | 100 lines |
| Writing or editing needs, requirements, verification items | [references/writing-requirements.md](references/writing-requirements.md) | 80 lines |
| How deep to write a requirement: features, values, inferred requirements, documents, gaps (beyond the rules below) | [references/requirement-depth.md](references/requirement-depth.md) | 90 lines |
| The fields of each kind of item, with examples | [references/schema.md](references/schema.md) | 145 lines |
| Handing over a review page, applying feedback, recording locks, raising conflicts | [references/review-and-locks.md](references/review-and-locks.md) | 75 lines |
| Running the auditors and reasoning checks | [references/auditing.md](references/auditing.md) | 40 lines |
| Reporting a problem with the toolkit | [references/reporting-problems.md](references/reporting-problems.md) | 30 lines |
| A checker finding you don't understand | [references/rules.md](references/rules.md) (find the code in its contents) | 250 lines |

## People

- **Who is the human author?** `spec status` prints who records are attributed to. If that's an agent's account, ask the engineer to set `git config syseng.author "Name <email>"`. Never set it yourself from memory, a commit log or a guess.
- **Pronouns.** Write "the engineer" or the person's name. Never infer pronouns from a name.

## Levels of intent

Every item has a level, computed from its records each time:
- **explicit:** a person locked it by name;
- **stated:** a person asked for it, and what they said, taken alone, says what it requires;
- **guided:** a person's choice or constraint fixed it without saying it;
- **derived:** something above it needs it, and no person addressed it;
- **added:** you or another agent added it unasked.

An item changed since its lock or intent record, and not kept, counts one level lower. Derived and added items are yours to reshape. Explicit and stated items are a person's direction: a change that alters them is a **conflict** and goes back to them with options. Guided items you may change, and you ask about the change once it's built. `spec show <ID>` gives an item's level, who gave it, and its history.

## The loop, for every change

1. **Open a change:** `spec change start "<the request, summarized>"`. Add `--mode spec-first` when the engineer wants to see the spec before code exists. One change is open at a time.
2. **Record what the engineer said** as intent on the items it directly expresses (below).
3. **Look for conflicts** with explicit and stated items in the affected elements, the elements that depend on them, and above them in the trace. Spec-first: raise each before building. Code-first: build, then raise each with rolling back among the options. No conflict: just build. See references/review-and-locks.md.
4. **Work.** Code as you normally would.
5. **Keep the spec in step, in the same change:** update the requirements and verification items the change affects, record a requirement (with `basis: added`) for each feature a user would notice that you add unasked, and a decision record for each design decision.
6. **Check:** the project's tests, then `spec check`. Fix every error.
7. **Audit:** fresh-context auditors review your spec updates (references/auditing.md). During onboarding, offer them with their cost instead (references/onboarding.md).
8. **Hand over** the review page and report in a few lines (references/review-and-locks.md).

When the engineer asks for something quickly, say so as soon as it's usable, then finish the tests and spec. Where and how you sequence the work is up to you.

## Capturing intent

What the engineer says becomes intent on the spec without an approval step; they correct it later on the review page.
- **Directly expresses, and no further.** "I want a self-driving car" is stated intent on the car driving itself, not on the trajectory planner. When unsure, record the lower level.
- **Summarize, never quote.** `said` is a close third-person summary: keep their hedges and strength, add nothing they didn't say, no double quotation marks.
- **Their reasoning, not just their "yes".** Where they gave reasons, summarize the reasons.
- **Context frames, it doesn't assert.** `context` says what was being discussed and what prompted the statement, and adds no claim they didn't make.
- **Say where intent came from.** What a person tells you is `source: human_conversation`. What you read in a document, code comment or commit counts as theirs only if they wrote or directed it; record its source kind, path and author (references/requirement-depth.md, part E).
- **Place each requirement under the system element it constrains,** however high the request began.
- **Connect to what's there.** When they ask for something existing items already account for, or restate one, name those items with their titles and add the request to them as intent.

## How deep to write requirements

1. **Depth follows intent.** Write what the engineer specified as deep as they went, in their terms, and never weaken it to match the code: a mismatch is an open decision. Write everything else at the level of behaviour someone relies on.
2. **One requirement per feature** a user or another program would notice, even unasked (`basis: added`, or `derived` when a stated need implies it). Count features, not effects: polish serving a requirement you already have needs none of its own.
3. **Exact values in a requirement** only if the engineer stated it, it's a safety limit, or a named consumer outside the element reads it.
4. **Other values stay in the code.** A verification item names a value only when a test that exists, or that you're adding, checks it. Values you find in existing code get at most one decision record per design topic, and only when someone would ask why; decisions you make while building each get their own.
5. **Subjective qualities** ("beautiful") are needs the engineer verifies by review, not requirements.
6. **A requirement you infer is derived:** cite the statement and propose it. When two designs would both satisfy the statement, ask instead of picking.
7. **A requirement belongs to the element whose code does it;** a system constraint is never restated in an element.
8. For anything these don't settle, read references/requirement-depth.md.

## Editing the spec

Never edit files under spec/ directly; `spec edit` is the only path. It shows each edit's context, asks for acknowledgments where needed, validates, and logs. One batch per call, in **block-style YAML** (a flow mapping such as `{said: a, b}` splits on commas):

```
spec edit <<'YAML'
edits:
  - add: requirement
    element: CHECK
    text: The checker shall report each duplicate ID.
    traces_to: PARSER-1
    intent:
      basis: stated
      context: Discussing what the checker should catch.
      said: Wants duplicate IDs reported.
    reason: the engineer asked for duplicate detection.
  - modify: CHECK-3
    set:
      text: The checker shall report each …
    rewording: true
    reason: …
YAML
```

- If it replies with an `acks:` block, read each item and send the batch again with a one-line note per item. If it rejects the batch, nothing was written; fix what the errors say.
- To change an explicit or stated item, name the resolved conflict (`conflict: D<n>`), add the person's own request as stated intent, or mark a pure rewording `rewording: true`.
- Every field of every kind is in references/schema.md.
- **Before you change an item,** weigh what `spec edit` and `spec show <ID>` say about it: its level, who gave it and how, how often it changed, and how much discussion is behind it.
- **Needs come only from the engineer's words,** never from your own ideas.
- Use a distinctive heredoc delimiter, such as `YAML`, so a batch can't collide with your own script's.

## Talking to the engineer

- Give every ID a short title: "SYS-7 (done gate)".
- Order questions by how much each answer would change, each with options and one recommended, plus a one-line way to accept everything. Use your harness's question menu if it has one. Record open decisions with `spec decide`, so they survive the conversation.
- **Anything you want the engineer to answer goes on a rendered page,** not in chat: record it with `spec decide`, hand over the review page, and give the link. Write each decision for a reader with none of your context: what is being decided, why it matters now, what each option does and what follows from it, with examples. If you'd only be informing them, a chat line is enough. Until they answer, `spec decide --replace D<n>` rewrites an open decision, and `spec decide --withdraw D<n> --reason "…"` withdraws one the conversation has overtaken.
- **Locks belong to the engineer.** Record one only when they named the items; never lock your own work. Details in references/review-and-locks.md.
- When asked "why is X like this?", answer from `spec show X`.

## Improving this skill

If something makes you jump through hoops, log it with `spec friction --workaround "…" --proposal "…"` and propose the change. Offer to report any problem with the toolkit, even one you worked around, as an issue (references/reporting-problems.md). Nothing here is fixed, except that people control what gets locked.
