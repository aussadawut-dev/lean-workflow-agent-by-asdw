# Changelog

Versions follow `MAJOR.MINOR.PATCH`. MAJOR changes workflow rules, MINOR adds rules or files, PATCH clarifies wording.

## 1.3.0

- Self-checks for the workflow files in `.github/lean-workflow/`:
  - `test-hooks.sh` — Quality Gate and SessionStart hook behavior in throwaway git repos.
  - `check-structure.sh` — referenced paths exist, settings valid, hooks executable, skill/agent frontmatter, gate markers.
- CI `.github/workflows/lean-workflow.yml` runs ShellCheck and both scripts when workflow files change.

## 1.2.0

- Policy files moved to `.agent/policy/`. `.agent/PROJECT.md` stays as the only project-owned file, so upgrades can replace `policy/` as a whole.

## 1.1.0

- Claude-native layer in `.claude/`, pointing into `.agent/` with no rule duplication:
  - `reviewer` subagent for independent `HIGH` review.
  - Skills: `/lean-init`, `/lean-task`, `/lean-review`, `/lean-gate`.
  - `SessionStart` hook suggests `/lean-init` while `PROJECT.md` is empty.
  - Permissions: allow read-only git commands, deny reading `.env` files.

## 1.0.0

- Baseline #1: Task Contract, Quality Gate, risk-based testing and review, progressive context.
- `CLAUDE.md` canonical, `AGENTS.md` adapter.
- Defaults for quality, budget, and risk.
- `Stop` hook Quality Gate driven by `PROJECT.md`.

## Upgrading

Workflow files are separate from project files, so an upgrade replaces them without touching your code.

1. Replace `.agent/policy/`, `.agent/README.md`, and `.agent/CHANGELOG.md`. Never replace `.agent/PROJECT.md`.
2. Replace `.claude/hooks/`, `.claude/agents/reviewer.md`, and `.claude/skills/lean-*/`. Keep your own agents and skills.
3. Replace `.github/lean-workflow/` and `.github/workflows/lean-workflow.yml`, unless you deleted them.
4. In `CLAUDE.md`, replace everything above `## Project additions`. Keep your additions.
5. Replace `AGENTS.md`, unless you edited it.
6. Merge `.claude/settings.json` by hand if you changed it.
7. Run `.github/lean-workflow/check-structure.sh` and `.github/lean-workflow/test-hooks.sh`.
8. Read the new `CHANGELOG.md` entry for MAJOR changes that need action.
