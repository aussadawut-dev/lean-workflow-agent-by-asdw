# Project Context

This file describes repository-specific information for agents.

Update it as the project takes shape. "Not defined" is not an error: it means the repository has no convention here yet. Do not invent one; when work establishes a real convention, record it here.

## Purpose

Lean Workflow Baseline: a repository template (Claude primary, `AGENTS.md` adapter for other agents) that gives a project a quality-driven coding workflow. It contains workflow files only, no application code. Current version: 1.4.0 (see `.agent/CHANGELOG.md`).

## Architecture

Shell scripts and Markdown only. No application, package manager, or build step.

- `CLAUDE.md` canonical agent contract; `AGENTS.md` adapter that defers to it.
- `.agent/` operating rules (`policy/` is replaced on upgrade; `PROJECT.md` is project-owned).
- `.claude/` `settings.json`, hooks (`quality-gate.sh` on `Stop`, `session-start.sh`), skills (`lean-init`, `lean-task`, `lean-review`, `lean-gate`), `reviewer` subagent.
- `.github/lean-workflow/` self-checks for the workflow files; `.github/workflows/lean-workflow.yml` runs them in CI when workflow files change.

## Commands

### Install
Not defined. No dependencies. CI uses `shellcheck` (preinstalled on `ubuntu-latest`; not installed locally).

### Build
Not defined.

### Test
`.github/lean-workflow/test-hooks.sh` tests the Quality Gate and SessionStart hooks (13 checks, ~1s). Verified: passes, exits non-zero on failure.

### Lint
`shellcheck .claude/hooks/*.sh .github/lean-workflow/*.sh` (CI only; `shellcheck` is not installed locally, so not run here).
`.github/lean-workflow/check-structure.sh` checks referenced paths, settings, hook executability, frontmatter, and `PROJECT.md` gate markers (~0.2s). Verified: passes, exits non-zero on failure.

### Typecheck
Not defined.

### Quality Gate

Commands run by the Claude `Stop` hook (`.claude/hooks/quality-gate.sh`) before a turn can finish. One command per line, fast checks first. Each must exit non-zero on failure (e.g. `test -z "$(gofmt -l .)"`, not `gofmt -l .`). Empty means the hook does nothing. Add commands once the project has them.

<!-- gate:start -->
```sh
.github/lean-workflow/check-structure.sh
.github/lean-workflow/test-hooks.sh
```
<!-- gate:end -->

## Important paths

- `CLAUDE.md`, `AGENTS.md` agent contract
- `.agent/policy/` workflow rules (do not edit per project)
- `.claude/hooks/` gate and session hooks
- `.github/lean-workflow/` self-check scripts

## High-risk areas

- `.claude/hooks/` and `.claude/settings.json`: run on every turn and control permissions; a bug can block all work or widen access.
- `.agent/policy/`: changes alter behavior for every downstream project on upgrade.

## Documentation routes

- `README.md` template usage, layout, checks
- `.agent/README.md` policy router
- `.agent/CHANGELOG.md` versions and upgrade steps
