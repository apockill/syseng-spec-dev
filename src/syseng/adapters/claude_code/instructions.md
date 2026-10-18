In Claude Code, the toolkit's hooks (`.syseng/hook`) run in this repository. They're guardrails, and the method works without them:

- **Spec guard:** a direct edit to a file the toolkit manages is refused, and the refusal names the command to use.
- **Done gate:** if the spec has errors when you finish a turn, you're sent back once with them. If you're stopping to ask the engineer something, ask then.
- **Approval reader:** a line of the engineer's message that approves items by ID, such as `approve CLI-9, DR-41` or `CLI-9 LGTM`, is recorded as their approval, and you're told so. Don't record it again. If it couldn't tell exactly which items a line meant, confirm the list with the engineer, then record their answer.
