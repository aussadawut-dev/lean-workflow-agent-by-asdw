# Tools

- Prefer dedicated file/search tools over shell equivalents when available.
- Run independent tool calls in parallel; sequence dependent ones.
- Use `python3 .lean/bin/lean` for every workflow operation; do not edit runtime state under `.agent-runtime/` by hand.
- Use the commands in `.lean/PROJECT.md` for build, test, lint, typecheck.
- Shared skills live in `.lean/skills/`, exposed by discovery links in `.claude/skills/` and `.agents/skills/`. Claude can use its `reviewer` subagent. Load policies on demand.
- Spawn agents only as `MODELS.md` allows; execution routing (`direct`/`delegated`), repository mode and review depth are independent.
- Do not add dependencies, frameworks, or process files unless the task requires them. Lean itself uses only the Python standard library, Bash and Git.
- Confirm before destructive or outward-facing actions.
