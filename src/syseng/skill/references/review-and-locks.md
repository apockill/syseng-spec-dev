# Conflicts, review pages, feedback and locks

## Contents
- Conflicts
- Handing over the review page
- Reporting
- Feedback from the review page
- Locks
- Proposing items to lock

## Conflicts

A request conflicts when it can't be met without changing the meaning of an explicit or stated item, or when it makes one impossible to meet. Drafting the request's spec edits first is the quickest way to find out: `spec edit --dry-run` shows each affected item's level.

- **Spec-first:** raise each conflict before building, and wait for the person's choice. `spec edit` refuses the change until then.
- **Code-first:** build, then raise each conflict with rolling back among the options. The check won't let the change finish until every altered explicit or stated item is named by a conflict.

Raise one with `spec decide`, block-style YAML on standard input:

```
spec decide <<'YAML'
kind: conflict
question: Checking duplicate titles changes CHECK-3 (duplicate IDs), which the engineer locked. Keep the change?
importance: It alters a locked item, and the checker's output is what the engineer reads.
involves: [CHECK-3]
options:
  - label: Keep the new wording
    recommended: true
    detail: CHECK-3 also covers titles.
    keeps: [CHECK-3]
  - label: Roll back
    detail: Titles get a requirement of their own instead.
    rolls_back: [CHECK-3]
YAML
```

An ordinary open decision is the same without `kind`, `keeps` and `rolls_back`. Every decision needs a question, an importance, at least two options and exactly one recommended.

## Handing over the review page

Where the project's tests can run, record their results first (references/test-results.md), or the page has no health to show. Then run `spec review`. It compares against the trunk unless you name a base, and states its base at the top of the page. For a pull request, name the pull request's own base, so a stacked pull request compares against the one beneath it: `spec review --against <its base branch>`.

Where your harness can publish a private web page, as Claude's artifacts do, publish it there and give the person the link. Otherwise give the file's location. **Every pull request that changes the spec gets its own page, linked at the top of its description:** the person reviews it there, so a pull request without one can't be reviewed. Publish a new page when the branch changes, and say what it compares against beside the link. Don't publish when your instructions confine you to the machine or a sandbox.

The page shows, in order: the conflicts and decisions awaiting the person, your responses to their last feedback, what changed since the base, the intent you captured, the items most worth locking, the system as a graph, and the full spec. Everything on it is available to you too: `spec review --section <awaiting|responses|changes|captured|proposals|graph|items>`, and `spec diff`.

## Reporting

Beside the page, report in a few lines:
- what changed;
- each measure the overview marks worse (`spec review --section overview`), with why and what you'd do about it;
- each conflict, with its options, the recommended one first;
- each alteration to an item a person locked, stated or guided, which they keep on the page (or with `lock <ID>`) or ask you to roll back;
- the items you propose for locking;
- any friction you hit.

## Feedback from the review page

The person pastes a fenced `syseng-feedback` block to you, or posts it on a pull request. Apply it as it is: `spec feedback apply` (the block on standard input, or `--file`). It records the locks, unlocks, kept alterations and decision choices in the person's name, refuses anything that changed since the page showed it, and lists what needs you as feedback items (F1, F2, …):
- do what each asks (a comment, a correction to an intent record, a roll-back), or explain why not;
- answer each with `spec feedback respond F<n> "…"`; the check keeps the change open until every one has a response;
- regenerate the page and hand it back.

An empty block means they reviewed and have nothing to add. Apply it anyway: it records the review.

## Locks

A lock is a person's own act, naming the items: a lock line in chat (`lock CHECK-3`, `CHECK-3 LGTM`), a menu choice that named them, the terminal, or the review page.
- Record one only when the engineer named the items: `spec lock <IDs> --via <chat|menu|terminal|page>`, with `--words` holding a summary of what they said, never their exact words. A harness hook may record lock lines itself; when it says it has, don't record them again.
- You never lock your own work, and a general "looks good" locks nothing, though it may be intent worth recording.
- When a lock names its exceptions by description ("everything except the wording ones"), leave out every item the description could cover, and confirm the exact list first.

## Proposing items to lock

Propose the items whose consequences reach the engineer (what they see, lock or do), judged from what you know they care about: `spec propose <IDs> --why "…"`, most consequential first. One reason per group of items; don't repeat it for each. Your decision records about mechanics stay yours to revise. The review page also lists the items the most of the tree hangs from, but that list is mechanical and no substitute for your judgment.
