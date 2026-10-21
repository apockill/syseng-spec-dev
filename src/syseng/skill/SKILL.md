---
name: syseng
description: Systems-engineering spec workflow for repositories that have a spec/ directory with spec/toolkit.yaml. Use it for every change to such a repository, whether you're writing code first or the spec first. Also use it when the engineer asks why something is the way it is, says what they want, locks spec items, wants a feature planned before it's built, or wants an existing project brought into the method.
---

# Working with a systems-engineering spec

The engineer steers this project by reading its requirements, not its code. The spec records how directly a person asked for each item, so that you can build fast and still know what you may reshape freely and what you must bring back to a person. Your job has two parts:
- keep the spec true to the code, and the code true to the spec;
- bring the engineer only what needs their judgment, in the order that matters most.

Run the toolkit as `spec` from the repository root. `spec <command> --help` explains any command, and its error messages say what's wrong, why, and how to fix it. If it reports that the toolkit isn't set up on this machine, pass that on to the engineer. `spec status` says who records are attributed to; if that's an agent's account rather than the person directing you, tell them to set `git config syseng.author "Name <email>"`.

## Levels of intent

Every item has a level, computed from its records each time:
- **explicit:** a person locked it by name;
- **stated:** a person asked for it, and what they said, taken alone, says what it requires;
- **guided:** a person's choice or constraint fixed it without saying it;
- **derived:** something above it needs it, and no person addressed it;
- **added:** you or another agent added it unasked, and nothing a person gave needs it.

An item changed since its lock or intent record, and not kept, counts one level lower: locked to an earlier version counts as stated. Once the person has seen the change on a review page and let it be, it stops asking them.

Derived and added items are yours to reshape. Explicit and stated items are a person's current direction: a change that alters them is a **conflict** and goes back to them with options. Guided items you may change, and you ask about the change once it's built. `spec show <ID>` gives an item's level, who gave it and when, and its history.

## The loop, for every change

1. **Open a change:** `spec change start "<the engineer's request, summarized>"`.
   - Add `--mode spec-first` when the engineer wants to see the spec before any code exists. Code-first is the default, and both are first class.
   - Only one change is open at a time.
2. **Record what the engineer said** as intent on the items it directly expresses (see "Capturing intent" below).
3. **Look for conflicts.** Compare the request with the explicit and stated items in the elements it affects, in the elements that depend on those, and above them in the trace. Drafting the request's spec edits first is the quickest way: the edit's context shows each affected item's level. A request conflicts when it can't be met without changing such an item's meaning, or when it makes one impossible to meet.
   - **Spec-first:** raise each conflict before building (`spec decide` with `kind: conflict`), and wait for the person's choice. `spec edit` refuses the change until then.
   - **Code-first:** build, and raise each conflict when the change is done, with rolling back among the options. The check won't let the change finish until every altered explicit or stated item is named by a conflict.
   - No conflict: just build. Never stop for one that isn't there.
4. **Work.** Code as you normally would. Read the spec when it helps, not as a ritual.
5. **Keep the spec in step as part of the same change.** Update the requirements and verification items the change affects, record a requirement (with `basis: added`) for each feature a user would notice that you add unasked, and add a decision record for each design decision you make. See "Editing the spec".
6. **Before calling the change done,** run every cheap check: the project's tests, then `spec check`. Fix every error.
7. **Before the engineer reviews,** have fresh-context auditors check your spec updates. See references/auditing.md.
8. **Hand over the review page.** Run `spec review` (add `--against main` on a branch) and give the person the page's location. It shows, in order: the conflicts and decisions awaiting them, your responses to their last feedback, what changed since their last review, the intent you captured, the items most worth locking, the system as a graph, and the full spec.
9. **Report** in a few lines, beside the page:
   - what changed;
   - each conflict, with its options, the recommended one first;
   - each alteration to an item a person locked, stated or guided, which they keep on the page (or with `lock <ID>`) or ask you to roll back;
   - the items you propose for locking;
   - any friction you hit.

When the engineer asks for something quickly, tell them as soon as it's usable, then finish the tests and spec.

How you sequence the work, where you make the change (branch, worktree or working tree) and how you use your harness are up to you. This skill states outcomes, not procedures.

## Capturing intent

What the engineer says becomes intent on the spec, without an approval step. They confirm or correct what you captured later.
- **Directly expresses, and no further.** "I want a self-driving car" puts stated intent on the requirement that the car drives itself, not on the trajectory planner beneath it. When you're unsure whether a statement directly expresses an item, record the lower level: guided rather than stated, nothing rather than guided.
- **Summarize, never quote.** Their words stay out of the repository. An intent record's `said` is a close, lightly cleaned summary in the third person: keep their hedges and strength (probably, must), add no number or mechanism they didn't give, and say what they left open when they said so. No double quotation marks.
- **Their reasoning, not just their "yes".** Where they gave reasons, summarize the reasons.
- **Context frames, it doesn't assert.** `context` says what was being discussed and what prompted the statement, and adds no claim they didn't make.
- **Place each requirement under the system element it constrains,** however high in the tree their request began. Requirements flow down the system breakdown: each refines a requirement of its element's parent.
- **Connect what they say to what's there.** When they ask for something existing items already account for, or restate one, name those items with their titles and add the request to them as intent.

## Feedback from the review page

The person copies a block from the page and pastes it to you, or posts it on a pull request. Apply it as it is: `spec feedback apply` (the block on standard input, or `--file`). It records the locks, unlocks, kept alterations and decision choices in the person's name, refuses anything that changed since the page showed it, and lists what needs you as feedback items (F1, F2, …):
- do what each one asks (a comment, a correction to an intent record, a roll-back), or explain why not;
- answer each with `spec feedback respond F<n> "…"`; the check keeps the change open until every one has a response, and their next page shows your answers;
- regenerate the page and hand it back.

A block with nothing in it means they reviewed it and have nothing to add. Apply it anyway: it records the review, so the next page shows only what changed since.

Everything on the page is available to you too: `spec review --section <awaiting|responses|changes|captured|proposals|graph|items>`, and `spec diff`.

## Editing the spec

Never edit files under spec/ directly. `spec edit` is the only path: it shows each edit's context, asks for acknowledgments where they're needed, validates the result and logs it. Send one batch per call:

```
spec edit <<'YAML'
edits:
  - add: requirement
    element: CHECK
    text: The checker shall report each duplicate ID.
    traces_to: PARSER-1                 # a requirement of the element's parent
    intent: {basis: stated, context: Reviewing the checker, said: Wants duplicate IDs reported.}
    reason: the engineer asked for duplicate detection.
  - add: requirement
    element: CHECK
    text: The checker shall report each duplicate title.
    traces_to: PARSER-1
    basis: added                       # or derived: something above needs it
    why: two items with one title are as confusing as two with one ID.
    reason: a related check nobody asked for.
  - modify: CHECK-3
    set: {text: "The checker shall …"}
    rewording: true                    # the meaning stays the same
    reason: …
  - remove: CHECK-9
    reason: …
YAML
```

- `intent:` fills in `by`, `when` and the item's fingerprint.
- **If it replies with an `acks:` block,** the edit changes the meaning of something a person gave or something others depend on. Read each item, then send the batch again with a one-line note per item.
- **If it rejects the batch,** fix what the errors say. Nothing was written.
- **To change an explicit or stated item,** name the resolved conflict with `conflict: D<n>`, add the person's own request for that change as stated intent, or mark a pure rewording `rewording: true`.
- **Use a distinctive heredoc delimiter,** such as `YAML`, so a batch can't collide with your own script's.
- **Needs come only from the engineer's words.** See references/writing-requirements.md.
- **Before you change an item, weigh what `spec edit` and `spec show <ID>` say about it:** its level, who gave it, when and how; how recently and how often it changed; how much discussion is behind it.

## Talking to the engineer

- **Give every ID a short title,** for example "SYS-7 (done gate)", and link to it where your medium allows. Nobody should have to look an ID up.
- **Order questions and flags by how much each answer would change,** most consequential first.
  - Give each one options, with exactly one recommended, and say why it ranks where it does.
  - Offer a one-line way to accept everything.
  - Use your harness's question menu if it has one.
- **Record open decisions in the change** with `spec decide` (question, importance, involves, options), so they survive the conversation. A conflict adds `kind: conflict`, names the items in `involves`, and gives each option `keeps:` and `rolls_back:` lists, so the person's choice is applied as chosen. The review page also lets them answer each involved item on its own.
- **Locks belong to the engineer.** A lock is a person's own act: a lock line in chat (`lock CHECK-3`, or `CHECK-3 LGTM`), a menu choice that named the items, the terminal, or the review page.
  - Record one only when the engineer named the items: `spec lock <IDs> --via <chat|menu|terminal|page>`, with `--words` holding a summary of what they said, never their exact words. A harness adapter may record lock lines itself; when it tells you it has, don't record them again.
  - You never lock your own work, and a general "looks good" locks nothing. It may still be intent worth recording.
  - When a lock names its exceptions by description ("everything except the wording ones"), leave out every item the description could refer to, and confirm the exact list first.
- **Don't ask for locks on everything.** Propose the items whose consequences reach the engineer (what they see, lock or do), judged from what you know they care about: `spec propose <IDs> --why "…"`, most consequential first. Your decision records about mechanics stay recorded and yours to revise. The review page also lists items that the most of the tree hangs from, but that list is mechanical and no substitute for your judgment.
- **When asked "why is X like this?",** answer from `spec show X`: its intent records, rationale, decision records and history.

## Improving this skill

You're one of this toolkit's main users. If something makes you jump through hoops, or the engineer uses the method in a way this skill doesn't cover, say so:
- log it with `spec friction --workaround "…" --proposal "…"`;
- propose, or make, the change to the skill or toolkit.

Nothing here is fixed, except that people control what gets locked.

## References

- references/writing-requirements.md: layers, wording rules, intent records, levels and verification items.
- references/auditing.md: the auditors and the reasoning checks.
- references/onboarding.md: bringing an existing project in.
- references/rules.md: every checker rule, and why it exists.
