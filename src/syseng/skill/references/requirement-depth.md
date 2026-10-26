# How deep to write requirements

The rules in SKILL.md settle most cases. This file covers the rest, with the tests behind each rule and worked examples.

## Contents
- A. What counts as a noticeable feature
- B. Where a value goes
- C. Requirements you infer
- D. Code that falls short, and conventions some parts break
- E. Intent read from documents
- F. Splitting a big element
- G. Worked examples

## A. What counts as a noticeable feature

- Test: if this feature disappeared tomorrow, would a user, an operator or another program notice without reading the code? Yes: one requirement. No: none.
- Count features, not effects. Polish that serves a requirement you already have (hover lift, parallax, easing, a 250 ms fade) needs no requirement of its own.
- Visible features, controls, shortcuts, settings that persist, errors people see, and data sent to or received from other systems count.
- Caches, internal retries, logs nobody reads and code structure don't, unless their effect is observable ("changes appear within a minute").
- Developer-only tools (a localhost-only debug page): note them; no requirement.
- Data sent to a third party counts even if invisible: write the requirement and ask the engineer about it.
- Unsure: write it as `added` and ask. Never drop a feature silently.

## B. Where a value goes

Decide per value; the first match wins.

1. The engineer stated it → the requirement, exactly.
2. A safety limit, or it guards an irreversible action → the requirement, exactly.
3. A named consumer outside this element reads or parses it: another program, a script, a stored file format, another team. JSON field names, exit codes, file formats, command and flag names → the requirement, exactly, in double quotes ("node_id", "meta.json") so the wording check reads them as quoted values, not code names. Options a UI happens to offer, animation timings and log text nobody parses don't count.
4. A test that exists, or that you are adding, checks the exact value → that verification item's description.
5. Someone would ask "why this number?" and the answer isn't obvious → the one decision record for that design topic (a "motion timings" record, never one record per value).
6. Otherwise → the code only. Most values end here.

## C. Requirements you infer

- When a stated need clearly implies a behaviour the engineer didn't spell out ("never runs away" implies Stop isn't delayed by other commands), write it with basis `derived`, cite the statement, and propose it for the engineer to confirm.
- Infer only what the statement directly needs. When two designs would both satisfy it (retry the stop, or alert the operator), raise an open decision with both; don't pick.

## D. Code that falls short, and conventions some parts break

- Where the code doesn't do what the engineer intended, keep the requirement as intended and raise one open decision naming the gap. Never reword a requirement, and never narrow a safety rule, to fit the code.
- Where a repository-wide convention (a constraint) is broken by a few parts, keep the constraint as written and raise one decision per constraint listing every part that breaks it, with options: fix the parts, record them as named exceptions, or change the constraint.
- Never restate a system constraint in an element's requirements, word for word or more weakly: it already applies to every element. An element's requirements add only what is specific to it.
- A requirement belongs to the element whose code does it. A script or program outside the element that reads its output is a named consumer (B.3), not a requirement there.

## E. Intent read from documents

- Intent is the engineer's only if they said it to you (source `human_conversation`) or wrote or directed the source. Record the source kind (`document`, `code_comment`, `commit_message`), its path, and the author `git log` shows (references/schema.md has the fields).
- A document the engineer wrote counts like their own words: `stated` where it alone says what the item requires, otherwise `guided`.
- A code comment or document that attributes a rule to the engineer by name ("the engineer's hard rule"): `guided`.
- A source an agent account wrote counts as directed by the engineer when it records that it came from them (a commit message such as "notes from session with the engineer"): `guided`.
- A source an agent account wrote, with nothing showing the engineer directed it: the item is `derived`, not the engineer's intent. Ask the engineer to confirm what matters.

## F. Splitting a big element

- Give an element children only when its requirements would pass about 30, and only along seams its tests already follow.
- The parent then gets a few requirements saying what the element does as a whole, each serving a need. They're real requirements, not placeholders written so children have something to refine.

## G. Worked examples

**A stop button, engineer said "never run away; if I lose the page or press Stop, it stops".** Code: Stop waits up to 5 s for control; the watchdog fires after 2 s and sends one stop, never retried; head and lift keep moving; speed clamped at 200 mm/s.
- stated: "When the engineer presses Stop, VECTOR shall stop the robot." "If the engineer loses the page, VECTOR shall stop the robot."
- derived, proposed: "When the engineer presses Stop, VECTOR shall send the stop without waiting to acquire behaviour control." The 2 s and 200 mm/s stay as safety limits, proposed for confirmation.
- open decisions: retry a failed stop, or alert the engineer? Does "it stops" include head and lift?
- not a requirement: the 500 ms heartbeat interval (code only).

**A portfolio, engineer said "beautiful, motion guides the eye"; the code has hover lifts, parallax, staggered reveals, a search shortcut, a dark-mode toggle, an image cache, a localhost debug page and third-party analytics.**
- one requirement for "motion guides the eye"; none for the lift, parallax or timings (polish serving it).
- `added` requirements for search, the remembered theme and the analytics, with a question about analytics consent.
- nothing for the cache or the debug page; "beautiful" is a need the engineer verifies by review.

**The same portfolio, engineer specified "A fades in, morphs into logo B over about a second, ease-in-out; the tagline types out; the cursor blinks twice; never block scrolling". The code blinks three times and locks scrolling.**
- four or five `stated` requirements in the engineer's words ("about one second", "blinks twice", "remains scrollable"); the code's 1.1 s and 40 ms per letter stay in the code.
- two open decisions: the code blinks three times, and it locks scrolling.

**A status endpoint the portal reads, and a CLI whose exit codes a cron script checks.** The JSON field names and the exit codes go in requirements exactly (named consumers). The UI's turn options (90°, 180°), a 250 ms animation and a log format nobody parses stay in the code. The cron script is the consumer, not a requirement of this element.
