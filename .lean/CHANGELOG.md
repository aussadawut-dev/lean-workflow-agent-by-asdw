# Changelog

Versions follow `MAJOR.MINOR.PATCH`. MAJOR changes workflow rules, or moves files an existing install depends on. MINOR adds rules or files. PATCH clarifies wording.

## 2.0.0

Layout only. No workflow rule changed, but every workflow path moved, so an existing install needs the migration below.

- `.agent/` is now `.lean/`: one namespace for the whole workflow, instead of rules in `.agent/` and self-checks in `.github/`.
- Self-checks left `.github/`, which now holds GitHub platform files only:
  - `.github/lean-workflow/check-structure.sh` -> `.lean/scripts/check-structure.sh`
  - `.github/lean-workflow/test-hooks.sh` -> `.lean/tests/test-hooks.sh`
- `check-structure.sh` also checks that the scripts in `.lean/scripts/` and `.lean/tests/` are executable, so a lost exec bit fails the structure check instead of CI.
- `CONTRIBUTING.md` and `.github/pull_request_template.md` added. The PR template is the Result Contract from `policy/CONTRACTS.md`, so the repository reports its own changes in the format it asks for.
- Zone names stay namespaced on purpose. A downstream project keeps its own `scripts/`, `tests/`, `docs/`, and root `CHANGELOG.md`, with nothing to rename and nothing to merge.
- Entries below describe the `.agent/` paths that were current at the time. They are left as written.

### Migrating from 1.x

1. `git mv .agent .lean`
2. `mkdir -p .lean/scripts .lean/tests`, then `git mv` `check-structure.sh` into `.lean/scripts/` and `test-hooks.sh` into `.lean/tests/`. Remove the empty `.github/lean-workflow/`.
3. Replace `.agent/` with `.lean/` in `CLAUDE.md`, `AGENTS.md`, `.claude/hooks/*.sh`, `.claude/skills/lean-*/SKILL.md`, `.claude/agents/reviewer.md`, and your own `.lean/PROJECT.md`.
4. Update the Quality Gate block in `.lean/PROJECT.md` and the paths in `.github/workflows/lean-workflow.yml`.
5. Run `.lean/scripts/check-structure.sh` and `.lean/tests/test-hooks.sh`.

## 1.4.0

Changes from dogfooding (a Go CLI, 5 headless runs). The Task Contract was never written, `TESTING.md` was never read, and policy files were rarely opened outside skills. Rules that work are the ones in `CLAUDE.md` and the hooks.

- `CLAUDE.md` now carries the critical rules inline:
  - a one-line contract as the first line before changing files;
  - regression tests for bug fixes, shown failing before the fix and passing after;
  - no reading of workflow internals unless the task needs them.
- The Task Contract is one line at every risk and quality level. In round 2 the one-liner was written in 4/4 runs; the full block added nothing.
- `/lean-task` is shorter and loads policy files only when needed.
- Gate failures: fix only what your change caused. Pre-existing or out-of-scope failures are reported as `BLOCKED`, never patched under hook pressure. In round 2 the Stop hook pushed Claude into editing an unrelated test file.
- Gate commands must exit non-zero on failure. `/lean-init` and `PROJECT.md` say so, with the `gofmt` example.
- README note on headless and CI use.

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

1. Replace `.lean/policy/`, `.lean/README.md`, `.lean/CHANGELOG.md`, `.lean/scripts/`, and `.lean/tests/`. Never replace `.lean/PROJECT.md`.
2. Replace `.claude/hooks/`, `.claude/agents/reviewer.md`, and `.claude/skills/lean-*/`. Keep your own agents and skills.
3. Replace `.github/workflows/lean-workflow.yml`, unless you deleted it.
4. In `CLAUDE.md`, replace everything above `## Project additions`. Keep your additions.
5. Replace `AGENTS.md`, unless you edited it.
6. Merge `.claude/settings.json` by hand if you changed it.
7. Run `.lean/scripts/check-structure.sh` and `.lean/tests/test-hooks.sh`.
8. Read the new `CHANGELOG.md` entry for MAJOR changes that need action.
