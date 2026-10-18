---
name: syseng
description: Systems-engineering spec workflow for repositories that have a spec/ directory with spec/toolkit.yaml. Use it for every change to such a repository, whether you're writing code first or the spec first. Also use it when the engineer asks why something is the way it is, approves spec items, wants a feature planned before it's built, or wants an existing project brought into the method.
---

# Working with a systems-engineering spec

The engineer steers this project by reading its requirements, not its code. Your job has two parts:
- keep the spec true to the code, and the code true to the spec;
- bring the engineer only what needs their judgment, in the order that matters most.

Run the toolkit as `.syseng/spec` from the repository root. `.syseng/spec <command> --help` explains any command, and its error messages say what's wrong, why, and how to fix it. If it reports that the toolkit isn't set up on this machine, pass that on to the engineer.

## The loop, for every change

1. **Open a change:** `.syseng/spec change start "<the engineer's request, summarized>"`.
   - Add `--mode spec-first` when the engineer wants to see the spec before any code exists.
   - Only one change is open at a time.
2. **Work.** In code-first mode, which is the default, code as you normally would. Read the spec when it helps (`.syseng/spec show <ID>`), not as a ritual.
3. **Keep the spec in step as part of the same change.** Update the requirements and verification items the change affects, and add a decision record for each design decision you make. See "Editing the spec" below.
4. **Before calling the change done,** run every cheap check: the project's tests, then `.syseng/spec check`. Fix every error.
5. **Before the engineer reviews,** have fresh-context auditors check your spec updates. See references/auditing.md.
6. **Report:**
   - what changed, with a link to the change record;
   - the open decisions, most consequential first;
   - any friction you hit.

Code-first never stops to ask. Finish the change and record your questions as open decisions. Spec-first does stop, when a contradiction is one the engineer would want to decide before more work happens.

When the engineer asks for something quickly, tell them as soon as it's usable, then finish the tests and spec.

How you sequence the work, where you make the change (branch, worktree or working tree) and how you use your harness are up to you. This skill states outcomes, not procedures.

## Editing the spec

Never edit files under spec/ directly. `.syseng/spec edit` is the only path: it shows each edit's context, asks for acknowledgments where they're needed, validates the result and logs it. Send one batch per call:

```
.syseng/spec edit <<'YAML'
edits:
  - add: requirement
    element: CHECK
    text: The checker shall report each duplicate ID.
    traces_to: SYS-7
    origin: agent       # or engineer, when it's their words; then quote them in `source:`
    why: duplicates make traces ambiguous.
    reason: the engineer asked for duplicate detection.
  - modify: CHECK-3
    set: {text: "The checker shall …"}
    reason: …
  - remove: CHECK-9
    reason: …
YAML
```

- **If it replies with an `acks:` block,** the edit changes the meaning of something approved or depended upon. Read each item, then send the batch again with a one-line note per item.
- **If it rejects the batch,** fix what the errors say. Nothing was written.
- **Use a distinctive heredoc delimiter,** such as `YAML`, so a batch can't collide with your own script's.
- **Needs come only from the engineer's words.** Turn what they say, and why they say it, into needs, requirements and verification items. See references/writing-requirements.md.
- **Before you modify or remove an approved requirement,** read its rationale, decisions and history with `.syseng/spec show <ID>`.

## Talking to the engineer

- **Give every ID a short title,** for example "SYS-7 (done gate)", and link to it where your medium allows. Nobody should have to look an ID up.
- **Order questions and flags by how much each answer would change,** most consequential first.
  - Give each one options, with exactly one recommended, and say why it ranks where it does.
  - Offer a one-line way to accept everything.
  - Use your harness's question menu if it has one.
- **Record open decisions in the change** with `.syseng/spec decide` (question, importance, involves, options), so they survive the conversation.
- **Approvals belong to the engineer.**
  - Record an approval only when the engineer has explicitly approved items that were named to them, and quote their words: `.syseng/spec approve <IDs> --words "<their words>" --via <chat|menu>`. Choosing an approval option in a menu counts when the question named the items; quote the question and the choice.
  - A bare "lgtm" isn't an approval, and you never approve your own work.
  - When an approval names its exceptions by description ("everything except the wording ones"), leave out every item the description could refer to, and confirm the exact list with the engineer before recording it.
  - When you ask the engineer to approve items, give them the exact line that records it, such as `approve CLI-9, DR-41` or `CLI-9 LGTM`. The same phrasing every time lets the engineer learn it.
  - A harness adapter may record typed approvals itself. When it tells you it has, don't record them again.
- **When asked "why is X like this?",** answer from `.syseng/spec show X`: its rationale, decision records and history.

## What this harness does for you

No toolkit hooks run in this harness, so nothing stops a direct edit to the spec or a finish with errors. Everything above is your job: record the engineer's approvals yourself, edit the spec only with `.syseng/spec edit`, and run `.syseng/spec check` before you report.

## Improving this skill

You're one of this toolkit's main users. If something makes you jump through hoops, or the engineer uses the method in a way this skill doesn't cover, say so:
- log it with `.syseng/spec friction --workaround "…" --proposal "…"`;
- propose, or make, the change to the skill or toolkit.

Nothing here is fixed, except that the engineer controls what gets approved.

## References

- references/writing-requirements.md: layers, wording rules, verification items and approvals.
- references/auditing.md: the auditors and the reasoning checks.
- references/onboarding.md: bringing an existing project in.
- references/rules.md: every checker rule, and why it exists.
