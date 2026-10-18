# Bringing an existing project in

Onboarding records what the project is, and why. It doesn't redesign anything. Do as much of the thinking as you can, so that the engineer only confirms the needs and approves the rest in one go. The rigor goes into the changes that follow.

1. **Open the change:** `spec change start "Onboard <project>"`. If `spec` doesn't exist yet, the repository hasn't been set up: ask the engineer to run `spec init`.
2. **Map the system elements** from the code's structure: one tree, with the project as the root, and `depends_on` for reuse.
3. **Draft needs from what the engineer has said and written:** README files, design notes, issue text. Mark each one as needing the engineer's confirmation. Needs are the engineer's, so draft them, don't invent them.
4. **Extract requirements** from the code, the tests and the comments, describing the current behavior. Don't propose changes. A requirement the project doesn't actually meet becomes an open decision, not a fix.
5. **Link the existing tests** as verification items. Every test should be linked to something.
6. **Recover the reasons.** Write decision records from code comments, the structure and the commit history. Where the reason can't be recovered, ask, but only the questions the project can't answer itself, ranked by how much each answer changes.
7. **Run every check**, including the expensive ones and all the auditors. Record each failing test or broken link as an open decision. Don't fix it.
8. **Hand over.** Tell the engineer:
   - the needs to confirm;
   - the ranked questions;
   - the one line that approves everything else.
