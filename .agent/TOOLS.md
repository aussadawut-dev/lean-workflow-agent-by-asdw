# Tools

- Prefer dedicated file/search tools over shell equivalents when available.
- Run independent tool calls in parallel; sequence dependent ones.
- Use `DIRECT` execution by default.
- Use subagents only for genuinely independent parallel work or isolated review/research. Not for simple, tightly coupled, or shared-context work.
- Use the commands in `PROJECT.md` for build, test, lint, typecheck.
- Do not add dependencies, frameworks, or process files unless the task requires them.
- Confirm before destructive or outward-facing actions.
