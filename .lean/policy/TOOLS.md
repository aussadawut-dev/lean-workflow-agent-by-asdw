# Tools

- Prefer dedicated file/search tools over shell equivalents when available.
- Run independent tool calls in parallel; sequence dependent ones.
- Follow configured execution: `direct` is the portable default; `delegated` requires Controller/worker routing under `/lean-multi-agent`. Repository mode and review depth are independent.
- In direct execution, use subagents for independent review/research or explicitly requested parallel work. In delegated execution, assign bounded work including small tasks to one worker. Concurrent workers require explicit user intent and independent, exclusively owned scopes.
- Use the commands in `.lean/PROJECT.md` for build, test, lint, typecheck.
- Both agents use shared skills in `.claude/skills/`; Codex adapters in `.agents/skills/` link the same procedures. Claude can use its `reviewer` subagent. Load policies on demand.
- Do not add dependencies, frameworks, or process files unless the task requires them.
- Confirm before destructive or outward-facing actions.
