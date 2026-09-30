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
- Workflow rules live in `.lean/`. Start at `.lean/README.md`.

Build your repository however you want. Lean Workflow does not prescribe language, framework, architecture, package manager, database, or deployment model.

As the project grows, agents fill in `.lean/PROJECT.md` with real commands and paths. Add your test/lint commands to its Quality Gate section to have the `Stop` hook enforce them.

## Headless and CI use

`claude -p` ignores `permissions.allow` in `.claude/settings.json` until the workspace is trusted. Open the repository once with interactive Claude and accept the trust dialog, or pass `--allowedTools` on the command line. Hooks, skills, and the reviewer subagent still load.

## Claude commands

| Command | Use |
|---|---|
| `/lean-init` | Fill `.lean/PROJECT.md` from the real repository |
| `/lean-task <task>` | Start non-trivial work with a Task Contract |
| `/lean-review` | Review at the depth risk and quality require |
| `/lean-gate` | Run the Quality Gate and report DONE or not |

## Layout

Three zones. Each has one job and one owner.

```
CLAUDE.md               Entrypoint for Claude. The canonical contract.
AGENTS.md               Adapter for Codex and other agents. Defers to CLAUDE.md.
CONTRIBUTING.md         How to change the workflow files.

.lean/                  ZONE 1 - the workflow. Tool-agnostic; any agent can read it.
  README.md             Router: which rule file to read, and when.
  PROJECT.md            Project context, commands, Quality Gate.      <- yours to edit
  CHANGELOG.md          Workflow versions and upgrade steps.
  policy/               The rules. Replaced wholesale on upgrade.      <- do not edit
  scripts/              check-structure.sh
  tests/                test-hooks.sh

.claude/                ZONE 2 - Claude runtime. Paths are fixed by Claude Code.
  settings.json         Hooks and permissions.
  hooks/                quality-gate.sh (Stop), session-start.sh (SessionStart)
  skills/               /lean-init, /lean-task, /lean-review, /lean-gate
  agents/               reviewer subagent

.github/                ZONE 3 - GitHub platform only.
  workflows/            CI for the workflow files, nothing else.
  pull_request_template.md
```

Everything else belongs to your project. Both zone names are namespaced on purpose: your own
`scripts/`, `tests/`, `docs/`, and root `CHANGELOG.md` never collide with the workflow's.

## Checks

The workflow files test themselves. CI runs only when workflow files change, so it stays out of
your project's CI. Run locally:

```sh
.lean/scripts/check-structure.sh   # referenced paths, dead paths, settings, frontmatter, exec bits
.lean/tests/test-hooks.sh          # Quality Gate and SessionStart hooks
```

## What to delete after copying

These belong to this template, not to your project:

- `.lean/scripts/`, `.lean/tests/`, and `.github/workflows/lean-workflow.yml` — self-checks for
  the workflow files themselves.
- `CONTRIBUTING.md` — how to contribute to this template.
- This `README.md` — replace it with your own. The workflow's description lives in `.lean/README.md`.

Keep `.github/pull_request_template.md`. It is the Result Contract, which is the format Lean
Workflow asks every change to report in.

## Upgrading

See `.lean/CHANGELOG.md`. Read the entry for the version you are moving to before you start: a
MAJOR entry carries migration steps that must run before the replace steps.
