# Reporting a problem with the toolkit

When the toolkit gets in your way, its maintainers can only fix what reaches them. Report anything that stopped you, confused you, slowed you down, or that you worked around without saying so: an error you couldn't act on, a rule that didn't fit, a step that took several tries, something you needed that the toolkit doesn't do. This is the one way to report these, and a report goes to the toolkit's maintainers as an issue.

## What a report is for

Describe what happened so a maintainer can find the real problem. They may solve it differently from anything you'd think of, so don't propose a solution, not even as a hint. "The batch was refused twice with this message, and I couldn't tell which field was wrong" helps. A missing feature is reported the same way, as what you needed and why. "Add a `--field` flag" asks them to judge your fix without the problem behind it.

## Steps

1. From the repository root, get the template, keeping the file in your scratch space and out of the repository: `spec issue --template > <scratch>/report.md`.
2. Fill in every section. A maintainer who has never seen this project should be able to follow the task and retrace your steps.
3. Rewrite everything in general terms. **The toolkit's repository is public.** Leave out names of the project, its products, people, hosts, paths and requirement text. Describe them by kind: "a web app's backend", "a requirement about a safety limit". The toolkit's own commands, messages and rule codes are fine; replace any project detail inside a quoted message with a placeholder such as `<ITEM>`.
4. Preview it, from the repository root: `spec issue <scratch>/report.md --title "A short, general title"`. It sends nothing and gives a code for that exact text. It refuses reports with empty or extra sections, email addresses, absolute paths, the author's name, or this repository's address. That check is a backstop and misses plenty (a bare project name, for one), so it doesn't replace step 3.
5. Show the engineer the title and the full text, say that it will be public, and ask whether to send it. Do this once your work is done, unless the problem blocks you.
6. Only if they agree to that text: run the same command with `--send <code>`. If the text changes, the code no longer fits: preview and ask again. If they decline, drop it; agreement for one report doesn't cover the next.

If it can't send (no GitHub CLI, not signed in), it prints the text for the engineer to file by hand.
