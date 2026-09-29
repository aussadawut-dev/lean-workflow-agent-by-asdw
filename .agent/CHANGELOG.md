# Changelog

Versions follow `MAJOR.MINOR.PATCH`. MAJOR changes workflow rules, MINOR adds rules or files, PATCH clarifies wording.

## 1.0.0

- Baseline #1: Task Contract, Quality Gate, risk-based testing and review, progressive context.
- `CLAUDE.md` canonical, `AGENTS.md` adapter.
- Defaults for quality, budget, and risk.
- `Stop` hook Quality Gate driven by `PROJECT.md`.

## Upgrading

Workflow files are separate from project files, so an upgrade replaces them without touching your code.

1. Replace every file in `.agent/` except `PROJECT.md`.
2. Replace `.claude/hooks/quality-gate.sh`.
3. In `CLAUDE.md`, replace everything above `## Project additions`. Keep your additions.
4. Replace `AGENTS.md`, unless you edited it.
5. Merge `.claude/settings.json` by hand if you changed it.
6. Read the new `CHANGELOG.md` entry for MAJOR changes that need action.
