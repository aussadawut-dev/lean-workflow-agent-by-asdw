# Project Context

This file describes repository-specific information for agents.

Update it as the project takes shape. "Not defined" is not an error: it means the repository has no convention here yet. Do not invent one; when work establishes a real convention, record it here.

## Workflow mode

`standard` | `tracker` | `full` -- what each one adds: `.lean/policy/MODES.md`. Asked once, on the first session that finds it unset, and recorded below. To change it later, edit the value by hand; nothing asks again.

<!-- mode:start -->
unset
<!-- mode:end -->

## Purpose

Lean Workflow Baseline: a repository template (Claude primary, `AGENTS.md` adapter for other agents) that gives a project a quality-driven coding workflow. It contains workflow files only, no application code. Current version: 2.5.0 (see `.lean/CHANGELOG.md`).

## Architecture

Shell scripts and Markdown only. No application, package manager, or build step.

- `CLAUDE.md` canonical agent contract; `AGENTS.md` adapter that defers to it.
- `.lean/` the workflow: `policy/` rules (replaced on upgrade), `PROJECT.md` (project-owned, and where the workflow mode is recorded), `CHANGELOG.md`, `bin/` the workflow's own tools (`mode.sh`, `queue.sh`), and `scripts/` + `tests/` self-checks.
- `.claude/` Claude runtime: `settings.json`, hooks (`quality-gate.sh` on `Stop`, `session-start.sh` on `SessionStart`, which seeds the gate's state cache and reads the workflow mode), skills (`lean-init`, `lean-task`, `lean-review`, `lean-gate`), `reviewer` subagent.
- `.github/` GitHub platform only: `workflows/lean-workflow.yml` runs the self-checks in CI when workflow files change; `pull_request_template.md`.

## Commands

### Install
Not defined. No dependencies. `shellcheck` is used by the gate and CI (`brew install shellcheck` locally; preinstalled on `ubuntu-latest`). A container without it -- Claude Code on the web is one -- makes the gate report an environment problem rather than a failure, and the change stays unlinted until it is installed (`apt-get install -y shellcheck`, verified in that container).

### Build
Not defined.

### Test
`.lean/tests/test-hooks.sh` tests the Quality Gate and SessionStart hooks (67 checks, ~6s).
`.lean/tests/test-mode.sh` tests the workflow mode config (24 checks, <1s). Verified: passes, and dropping mode.sh's strip of a hand-edited value fails a check.
`.lean/tests/test-queue.sh` tests the `full` mode queue against a bare remote and two clones (38 checks, ~4.5s). Verified: passes, and force-pushing the claim commit instead of losing the race fails six checks.
 Verified: passes, exits non-zero on failure, and every term of the gate's state hash plus both of its refusal guards are covered -- removing any one of them fails a check. The gate's two verdicts are covered as a pair: a command the shell cannot find must be reported as an environment problem, and a command that exists and fails must not be -- including a wrapper that hands back another program's 127. Every term deciding that split is pinned on its own: remove the status test, either half of the command-name test, the resolve test or the assignment strip and a check fails.

### Lint
`shellcheck .claude/hooks/*.sh .lean/bin/*.sh .lean/scripts/*.sh .lean/tests/*.sh` (0.11.0; passes at default severity, same as CI).
`.lean/scripts/check-structure.sh` checks referenced paths, retired paths, settings, hook and tool executability, frontmatter, `.gitignore` entries for the gate's state files, and `PROJECT.md` gate and mode markers plus the recorded mode value (~0.3s). Verified: passes, exits non-zero on failure.

### Typecheck
Not defined.

### Quality Gate

Commands run by the Claude `Stop` hook (`.claude/hooks/quality-gate.sh`) before a turn can finish. One command per line, fast checks first. Each must exit non-zero on failure (e.g. `test -z "$(gofmt -l .)"`, not `gofmt -l .`). Empty means the hook does nothing. Add commands once the project has them.

<!-- gate:start -->
```sh
shellcheck .claude/hooks/*.sh .lean/bin/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-mode.sh
.lean/tests/test-hooks.sh
.lean/tests/test-queue.sh
```
<!-- gate:end -->

## Important paths

- `CLAUDE.md`, `AGENTS.md` agent contract
- `.lean/policy/` workflow rules (do not edit per project)
- `.claude/hooks/` gate and session hooks
- `.lean/bin/` workflow tools that run in a session: `mode.sh`, `queue.sh`
- `.lean/scripts/`, `.lean/tests/` self-checks for the workflow files

## High-risk areas

- `.claude/hooks/` and `.claude/settings.json`: run on every turn and control permissions; a bug can block all work or widen access.
- `.lean/bin/queue.sh`: writes commits and pushes them; a bug in the claim protocol lets two sessions work the same item, or blocks an item nobody holds.
- `.lean/policy/`: changes alter behavior for every downstream project on upgrade.

## Documentation routes

- `README.md` template usage, layout, checks
- `.lean/README.md` policy router
- `.lean/CHANGELOG.md` versions and upgrade steps
- `CONTRIBUTING.md` how to change the workflow files
