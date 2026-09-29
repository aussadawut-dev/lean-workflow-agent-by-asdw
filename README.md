# Lean Workflow Agent by ASDW

A repository starter for Claude (primary) with a quality-driven coding workflow. Other agents that read `AGENTS.md` follow the same contract.

## Start

Create a new repository from this one without its history:

- GitHub: **Use this template** button, or
- `npx degit aussadawut-dev/lean-workflow-agent-by-asdw my-project`, or
- `git clone` then `rm -rf .git && git init`

Then open it with Claude. That's it.

- Claude reads `CLAUDE.md` (canonical) and `.claude/` (hooks, skills, reviewer subagent).
- Codex and other agents read `AGENTS.md`, which defers to `CLAUDE.md`.
- Workflow rules live in `.agent/`. Start at `.agent/README.md`.

Build your repository however you want. Lean Workflow does not prescribe language, framework, architecture, package manager, database, or deployment model.

As the project grows, agents fill in `.agent/PROJECT.md` with real commands and paths. Add your test/lint commands to its Quality Gate section to have the `Stop` hook enforce them.

## Claude commands

| Command | Use |
|---|---|
| `/lean-init` | Fill `.agent/PROJECT.md` from the real repository |
| `/lean-task <task>` | Start non-trivial work with a Task Contract |
| `/lean-review` | Review at the depth risk and quality require |
| `/lean-gate` | Run the Quality Gate and report DONE or not |

## Layout

```
CLAUDE.md          Canonical entrypoint (Claude)
AGENTS.md          Adapter for Codex / other agents
.agent/            Operating rules for agents (not application code)
  PROJECT.md       Project context, commands, Quality Gate (yours to edit)
  policy/          Workflow rules (replaced on upgrade)
.claude/
  settings.json    Hooks and permissions
  hooks/           Quality Gate (Stop) and SessionStart hooks
  skills/          /lean-init, /lean-task, /lean-review, /lean-gate
  agents/          reviewer subagent
.github/
  workflows/lean-workflow.yml   CI for the workflow files only
  lean-workflow/                Hook tests and structure checks
```

Everything else belongs to your project.

## Checks

The workflow files test themselves. CI runs only when workflow files change, so it stays out of your project's CI. Run locally:

```sh
.github/lean-workflow/check-structure.sh   # referenced paths, settings, frontmatter
.github/lean-workflow/test-hooks.sh        # Quality Gate and SessionStart hooks
```

Delete `.github/lean-workflow/` and `.github/workflows/lean-workflow.yml` if you do not want them. Replace this README with your project's own; the workflow description lives in `.agent/README.md`.

## Upgrading

See `.agent/CHANGELOG.md`.
