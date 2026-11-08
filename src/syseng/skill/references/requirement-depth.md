# How deep to write requirements

The rules in SKILL.md settle most cases. This file covers the rest, with the tests behind each rule and worked examples.

## Contents
- A. What counts as a noticeable feature
- B. Where a value goes, by level, and staying environment-neutral
- C. Requirements you infer
- D. Code that falls short, and conventions some parts break
- E. Intent read from documents
- F. Splitting a big element or a long requirement
- G. Worked examples

## A. What counts as a noticeable feature

- Test: if this feature disappeared tomorrow, would a user, an operator or another program notice without reading the code? Yes: one requirement. No: none.
- Count features, not effects. Polish that serves a requirement you already have (hover lift, parallax, easing, a 250 ms fade) needs no requirement of its own.
- Visible features, controls, shortcuts, settings that persist, errors people see, and data sent to or received from other systems count.
- Caches, internal retries, logs nobody reads and code structure don't, unless their effect is observable ("changes appear within a minute").
- Developer-only tools (a localhost-only debug page): note them; no requirement.
- Data sent to a third party counts even if invisible: write the requirement and ask the engineer about it.
- Unsure: write it as `added` and ask. Never drop a feature silently.

## B. Where a value goes, by level, and staying environment-neutral

A requirement says what is needed at its level, or what must be prevented. Check each against the engineer's test: "I should be able to look at any requirement, and with a little bit of context, agree 'yes this is a feature/something/an intent/etc that should exist/that I agree with' without also having to wonder if I also necessarily agree with the implementation details."

**By level** (after INCOSE's Guide to Writing Requirements: solution-free, appropriate to its level, "your what is my how").
- **Needs and system requirements** are solution-free and environment-neutral: the capability, or the risk prevented. "Each app shall be reachable at its own address", not the proxy, the domain or the socket.
- **A how at the top** only as a constraint the engineer imposed, carrying their intent ("the toolkit shall be written in Python", because they said so). A convention you find in the code with nobody's intent behind it is a decision record, or a question for the engineer, not a constraint.
- **Lower levels.** A choice made at one level is a legitimate what for the level below. A requirement may name an exact name or value when it sits at the level where that choice applies (the lowest element that makes it) and a decision record at that level or above gives the reason. List the requirement in the record's `requirements`, and allow W009 on it citing the record when the checker flags the name. For an interface, the record lists the interface's standard names and values once, and the requirements that use them reference it.
- **Otherwise** the value goes in the verification item, which asserts it, and the requirement states the capability. "The CLI shall accept a batch on standard input" is the requirement; the flag, and the test that pipes a batch through it, are the verification item's.

Decide per value; the first match wins.

1. The engineer stated a quantity or a behaviour ("about one second", "blinks twice") → the requirement, in their words. A name they chose (a typeface, a library, a path) → a constraint carrying their intent if it binds the whole system, otherwise a decision record carrying it; requirements at the level where it applies may then name it.
2. A safety limit, or it guards an irreversible action → the requirement, exactly.
3. Another program relies on this exact value: JSON keys a client reads, exit codes a script checks, a file another tool opens → an interface requirement on the element that defines the interface, at the lowest level, saying which program relies on it. It names the value when a decision record lists the interface's standard values (rule 5); otherwise it says there is one standard value, and the verification item asserts it. Command and flag names a person types, files only the element itself reads, options a UI happens to offer, animation timings and log text nobody parses aren't interfaces: state the capability.
4. A test that exists, or that you are adding, checks the exact value → that verification item's description. Verification items test the implementation, so they may be as prescriptive as the tests: flags, paths, field names, values.
5. Someone would ask "why this number?" and the answer isn't obvious, or it's an interface's standard value → a decision record. For values found in existing code during a migration, one record per design topic (a "motion timings" record, an "app interface" record), never one per value. Decisions you make while building each get their own record, however many there are.
6. Otherwise → the code only. Most values end here.

**Environment-neutral.** Needs and requirements, at every level, name no host, domain, operating system, package manager, proxy or other deployment specific, so the spec stays true when the product moves. Say what the deployment must provide ("each app shall be reachable at its own address"), and leave the machinery to the code and the verification items. A need's context may give example deployments ("for example, on a home server").

## C. Requirements you infer

- When a stated need clearly implies a behaviour the engineer didn't spell out ("never runs away" implies Stop isn't delayed by other commands), write it with basis `derived`, cite the statement, and propose it for the engineer to confirm.
- Infer only what the statement directly needs. When two designs would both satisfy it (retry the stop, or alert the operator), raise an open decision with both; don't pick.

## D. Code that falls short, and conventions some parts break

- Where the code doesn't do what the engineer intended, keep the requirement as intended and raise one open decision naming the gap. Never reword a requirement, and never narrow a safety rule, to fit the code.
- Where a repository-wide convention (a constraint) is broken by a few parts, keep the constraint as written and raise one decision per constraint listing every part that breaks it, with options: fix the parts, record them as named exceptions, or change the constraint.
- Never restate a system constraint in an element's requirements, word for word or more weakly: it already applies to every element. An element's requirements add only what is specific to it.
- A requirement belongs to the element whose code does it. A script or program outside the element that reads its output is the reader an interface requirement names (B.3), not a requirement there.

## E. Intent read from documents

- Intent is the engineer's only if they said it to you (source `human_conversation`) or wrote or directed the source. Record the source kind (`document`, `code_comment`, `commit_message`), its path, and the author `git log` shows (references/schema.md has the fields).
- A document the engineer wrote counts like their own words: `stated` where it alone says what the item requires, otherwise `guided`.
- A code comment or document that attributes a rule to the engineer by name ("the engineer's hard rule"): `guided`.
- A source an agent account wrote counts as directed by the engineer when it records that it came from them (a commit message such as "notes from session with the engineer"): `guided`.
- A source an agent account wrote, with nothing showing the engineer directed it: the item is `derived`, not the engineer's intent. Ask the engineer to confirm what matters.

## F. Splitting a big element or a long requirement

- Give an element children when it's too big for a reader to take in as one, along the parts a reader would recognize in what the element does.
- The parent then gets a few requirements saying what the element does as a whole, each serving a need. They're real requirements, not placeholders written so children have something to refine.
- A requirement is one thought. One that joins two behaviours with "and", "or" or ";", or lists cases, becomes a parent stating the intent and children for the parts. Write the parent first: if you can't say its intent in one line, the split is wrong.
- A parent with one child is suspect: the child restates it (merge them), or a sibling is missing (find it).

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

**A CLI whose exit codes a cron script checks, and a status endpoint the portal reads.** One requirement listing every exit code joins several behaviours: write a parent, "Each outcome a calling script must tell apart shall have its own exit status", then one child per outcome. The children sit at the CLI, the lowest level where the codes are chosen, so each may name its code ("When the app can't be reached, the CLI shall exit with status 3") because a decision record lists the CLI's exit codes and why. The status endpoint's requirement may likewise name its keys, citing the record that lists them. Without such a record, each says there is one standard code or key and which program relies on it, and its verification item asserts the value. The cron script is the reader, not a requirement of this element. The UI's turn options (90°, 180°), a 250 ms animation and a log format nobody parses stay in the code.

**Web apps on a home server behind a reverse proxy, each with a manifest and a socket.** System requirements: "Each app shall be reachable at its own address"; "A new app shall go online without configuration outside its own directory". The host's operating system, the proxy and the domain appear in no need or requirement; a need's context may say the apps run on a home server, as an example. "Each app shall declare what it needs in a manifest that follows one schema, checked at startup" is a parent; its schema's parts are children, not one long requirement. At the app element, "Each backend app shall serve its API on a socket named app.sock at the top of its directory" is fine when a decision record listing the app interface's standard names gives that name and why; without one, the requirement says the socket has one standard name and the verification item asserts app.sock. A typeface the engineer chose in a style guide they wrote is a constraint carrying their intent; one found only in the code stays there, and a requirement says what the type serves ("numbers in a table line up").

**A long reasoning check, and one that looked manual.** A reasoning check asking five questions is five checks: give each its own item, under the requirement it verifies. Before writing a reasoning check or a manual item, look for an automated test or a static check (a linter over the spec or the code) that could do it; when none can, the item says why.
