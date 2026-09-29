# Lean Workflow Agent by ASDW

A repository starter for Claude (primary) with a quality-driven coding workflow. Other agents that read `AGENTS.md` follow the same contract.

## Start

Create a new repository from this one without its history:

- GitHub: **Use this template** button, or
- `npx degit aussadawut-dev/lean-workflow-agent-by-asdw my-project`, or
- `git clone` then `rm -rf .git && git init`

Then open it with Claude. That's it.

- Claude reads `CLAUDE.md` (canonical) and the `Stop` hook in `.claude/settings.json`.
- Codex and other agents read `AGENTS.md`, which defers to `CLAUDE.md`.
- Workflow rules live in `.agent/`. Start at `.agent/README.md`.

Build your repository however you want. Lean Workflow does not prescribe language, framework, architecture, package manager, database, or deployment model.

As the project grows, agents fill in `.agent/PROJECT.md` with real commands and paths. Add your test/lint commands to its Quality Gate section to have the `Stop` hook enforce them.

## Layout

```
CLAUDE.md          Canonical entrypoint (Claude)
AGENTS.md          Adapter for Codex / other agents
.agent/            Operating rules for agents (not application code)
.claude/           Claude settings and Quality Gate hook
```

Everything else belongs to your project. Replace this README with your project's own; the workflow description lives in `.agent/README.md`.

## Upgrading

See `.agent/CHANGELOG.md`.
