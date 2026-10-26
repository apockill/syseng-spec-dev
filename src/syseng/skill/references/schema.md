# Fields of each kind of item

Every add goes through `spec edit` as `- add: <kind>`; IDs are allocated for you unless you give `id:`. Use block-style YAML throughout, and quote a value that starts with a backtick or contains `: `.

## Contents
- need
- system requirement and constraint
- requirement (an element's)
- vi (verification item)
- decision (record)
- element
- intent records
- open decisions (`spec decide`)
- settings (`spec/toolkit.yaml`)

## need

A need is an outcome the engineer wants, in their terms. Filed on the root element, numbered NEED-n.

```
- add: need
  text: The engineer needs to put a new web app online by creating one directory.
  context: Their reasoning and scenarios of use, paraphrased.
  intent: …            # see "intent records"
  reason: …
```

## system requirement and constraint

On the root element. A system requirement says what the whole system shall do and `serves` needs; a constraint limits the solution (a language, a platform, a convention every part follows) and may serve none.

```
- add: system          # or: constraint
  text: Each app shall accept HTTP requests only on a socket in its own directory.
  serves: [NEED-1]
  basis: derived       # or intent: …
  why: the reverse proxy finds apps by their socket.
  reason: …
```

## requirement (an element's)

Refines exactly one requirement of its element's parent (for an element directly under the root, a system requirement or constraint).

```
- add: requirement
  element: BOX
  text: The tool shall offer one command for each API route of each running app.
  traces_to: SYS-7
  basis: derived
  why: SYS-7 asks for the routes as commands.
  reason: …
```

Optional: `verification_deferred: <why>` marks a requirement as knowingly unverified for now (no test is possible here, or it waits on hardware); the checker then stops listing it as a to-do. Use it sparingly, with a real reason.

## vi (verification item)

```
- add: vi
  element: BOX
  verifies: [BOX-3, BOX-4]
  method: test             # test, analysis, demonstration or inspection
  technique: unit test     # unit test, integration test, reasoning check or manual
  description: A command built from a route sends that route's request and prints its JSON reply.
  tests:
    python: [tests/test_box.py::test_route_command]   # key: the implementation's name in toolkit.yaml
  reason: …
```

- A **reasoning check** has no tests; its `description` is the prompt a fresh model answers pass or fail, naming the files or commands it judges.
- A **manual** item says what a person does and observes. It isn't verification until someone has done it.
- Describe only what the tests or prompt actually check. "Checks X" when the test checks half of X is the most common audit finding.

## decision (record)

A design decision and its reasons. Filed under the first of its `elements`, numbered DR-n.

```
- add: decision
  title: Apps are found by directory, not by a registry
  decided_by: agent          # engineer or agent
  elements: [SYS]
  requirements: SYS-7
  context: What prompted it.
  decision: What was decided.
  alternatives: What else was considered, and why not.
  consequences: What follows from it.
  basis: derived             # or intent: …
  reason: …
```

`decided_by: engineer` only when the engineer made the choice; a decision you recovered from code or commits is `agent` unless they confirm it.

## element

```
- add: element
  id: BOX                    # upper case, short; becomes the prefix of its items
  title: The box CLI
  parent: SYS
  depends_on: [TPL]          # reuse, never a second parent
  purpose: One sentence: what this part of the system is for.
  related_code:
    python: [box.py, _lib/boxkit/]
  reason: …
```

## intent records

On any item a person addressed. `spec edit` fills in `by`, `when` and `fingerprint`.

```
intent:
  basis: stated              # or guided
  context: What was being discussed and what prompted it; for a document, which one and who wrote it.
  said: A close third-person summary, never a quote.
```

An item no person addressed carries `basis: derived` (something above needs it) or `basis: added` (your own idea), with `why:` saying which. A decision record takes `basis` but no `why`: its context and decision are the reasons.

## open decisions (`spec decide`)

Questions for the engineer, logged in the open change. See references/review-and-locks.md for a full example.

```
question: …
importance: Why it ranks where it does.
involves: [ITEM-1]           # the items it's about
options:
  - label: …
    recommended: true        # exactly one
    detail: …
  - label: …
```

Add `kind: conflict`, and `keeps:` / `rolls_back:` per option, for a conflict with a locked or stated item. An open decision can't be edited once filed, so dry-run your thinking first.

## settings (`spec/toolkit.yaml`)

Edited by hand; `spec edit` doesn't cover it.
- `implementations`: each with `name`, `language`, `root` and one `primary: true`. The `name` is the key under each verification item's `tests`.
- `element_order`: the order elements are listed in.
- `flow_down: enforced` makes a requirement that skips a level an error.
