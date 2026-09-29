# Changelog

Versions follow `MAJOR.MINOR.PATCH`. MAJOR changes workflow rules, MINOR adds rules or files, PATCH clarifies wording.

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

1. Replace every file in `.agent/` except `PROJECT.md`.
2. Replace `.claude/hooks/`, `.claude/agents/reviewer.md`, and `.claude/skills/lean-*/`. Keep your own agents and skills.
3. In `CLAUDE.md`, replace everything above `## Project additions`. Keep your additions.
4. Replace `AGENTS.md`, unless you edited it.
5. Merge `.claude/settings.json` by hand if you changed it.
6. Read the new `CHANGELOG.md` entry for MAJOR changes that need action.
