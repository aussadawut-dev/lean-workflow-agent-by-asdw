# Project Context

This file describes repository-specific information for agents.

Update it as the project takes shape. "Not defined" is not an error: it means the repository has no convention here yet. Do not invent one; when work establishes a real convention, record it here.

## Purpose

Lean Workflow Baseline: a repository template (Claude primary, `AGENTS.md` adapter for other agents) that gives a project a quality-driven coding workflow. It contains workflow files only, no application code. Current version: 2.5.0 (see `.lean/CHANGELOG.md`).

## Architecture

Shell scripts and Markdown only. No application, package manager, or build step.

- `CLAUDE.md` canonical agent contract; `AGENTS.md` adapter that defers to it.
- `.lean/` the workflow: `policy/` rules (replaced on upgrade), `PROJECT.md` (project-owned), `CHANGELOG.md`, and `scripts/` + `tests/` self-checks.
- `.claude/` Claude runtime: `settings.json`, hooks (`quality-gate.sh` on `Stop`, `session-start.sh` on `SessionStart`, which seeds the gate's state cache), skills (`lean-init`, `lean-task`, `lean-review`, `lean-gate`), `reviewer` subagent.
- `.github/` GitHub platform only: `workflows/lean-workflow.yml` runs the self-checks in CI when workflow files change; `pull_request_template.md`.

## Commands

### Install
Not defined. No dependencies. `shellcheck` is used by the gate and CI (`brew install shellcheck` locally; preinstalled on `ubuntu-latest`). A container without it -- Claude Code on the web is one -- makes the gate report an environment problem rather than a failure, and the change stays unlinted until it is installed (`apt-get install -y shellcheck`, verified in that container).

### Build
Not defined.

### Test
`.lean/tests/test-hooks.sh` tests the Quality Gate and SessionStart hooks (55 checks, ~5.3s). Verified: passes, exits non-zero on failure, and every term of the gate's state hash plus both of its refusal guards are covered -- removing any one of them fails a check. The gate's two verdicts are covered as a pair: a command the shell cannot find must be reported as an environment problem, and a command that exists and fails must not be -- including a wrapper that hands back another program's 127. Every term deciding that split is pinned on its own: remove the status test, either half of the command-name test, the resolve test or the assignment strip and a check fails.
`.lean/tests/test-structure.sh` tests the model registry age check in `.lean/scripts/check-structure.sh` (11 checks, ~2.9s), each in a throwaway copy of the repository. Verified: passes, exits non-zero on failure, and the window, its edge, the future-date guard and the half-a-registry guard each fail a check when removed. It also runs the check against this repository, so the suite goes red on the day the shipped registry goes stale rather than only the gate.

### Lint
`shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh` (0.11.0; passes at default severity, same as CI).
`.lean/scripts/check-structure.sh` checks referenced paths, retired paths, settings, hook executability, frontmatter, `.gitignore` entries for the gate's state files, `PROJECT.md` gate markers, and the age of the model registry below (~0.3s). Verified: passes, exits non-zero on failure.

### Typecheck
Not defined.

### Quality Gate

Commands run by the Claude `Stop` hook (`.claude/hooks/quality-gate.sh`) before a turn can finish. One command per line, fast checks first. Each must exit non-zero on failure (e.g. `test -z "$(gofmt -l .)"`, not `gofmt -l .`). Empty means the hook does nothing. Add commands once the project has them.

<!-- gate:start -->
```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-hooks.sh
.lean/tests/test-structure.sh
```
<!-- gate:end -->

## Model registry

Which model each tier in `.lean/policy/MODELS.md` resolves to when a subagent is spawned. Aliases, not pinned version ids: an alias tracks the current generation, a pinned id goes out of date without saying so. Re-verify the entries against the models the session actually offers, then move `verified` forward; `.lean/scripts/check-structure.sh` fails once that date is more than 90 days old.

<!-- models:start -->
verified: 2026-09-30

| tier | model |
| --- | --- |
| fast | haiku |
| default | sonnet |
| strongest | opus |
<!-- models:end -->

## Important paths

- `CLAUDE.md`, `AGENTS.md` agent contract
- `.lean/policy/` workflow rules (do not edit per project)
- `.claude/hooks/` gate and session hooks
- `.lean/scripts/`, `.lean/tests/` self-checks for the workflow files

## High-risk areas

- `.claude/hooks/` and `.claude/settings.json`: run on every turn and control permissions; a bug can block all work or widen access.
- `.lean/policy/`: changes alter behavior for every downstream project on upgrade.

## Documentation routes

- `README.md` template usage, layout, checks
- `.lean/README.md` policy router
- `.lean/CHANGELOG.md` versions and upgrade steps
- `CONTRIBUTING.md` how to change the workflow files
