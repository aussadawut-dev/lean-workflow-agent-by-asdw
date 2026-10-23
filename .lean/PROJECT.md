# Project Context

Project-owned facts and routes. Keep this map short; read the linked reference only when relevant. "Not defined" means no convention exists yet.

## Purpose

Lean Workflow Baseline 4.15.0: a portable Claude/Codex workflow template. This repository contains workflow files, no application code or Web/API/Database areas.

## Architecture

Bash, Python 3.9+ standard library, JSON and Markdown. AGENTS.md is canonical; CLAUDE.md imports it. Shared skills live in `.lean/skills/`, discovered through runtime symlinks. The active agent owns the task; execution defaults to direct. Detailed tooling and test coverage: `docs/workflow-development.md`.

## Commands

- Install: no application dependencies. Require Bash, Git, Python 3.9+ and shellcheck. Native Windows is unsupported; environment notes are in `docs/workflow-development.md`.
- Build / Typecheck: not defined.
- Test: `python3 -m unittest discover -s .lean/tests -p 'test_*.py'`, or `python3 .lean/tests/run_tests.py` to run files in parallel (`--shards N` splits each file across N processes; named `*.sh` suites run with bash). Run the full suite before reviewing workflow behavior changes; CI also runs it.
- Hooks: `.lean/tests/test-hooks.sh` uses temporary repositories and runs its case parts concurrently.
- Lint: `shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh` and `.lean/scripts/check-structure.sh`.
- Mode validation: `python3 .lean/scripts/workflow.py show` / `check`.

## Quality Gate

Codex runs the shared gate explicitly; Claude uses the Stop adapter. The turn gate checks hook/discovery integrity. The full Python suite above is additionally required before shipping workflow behavior changes. Missing tools/checks block; see `policy/QUALITY.md` for enforcement and already-approved gate-control changes.

<!-- gate:start -->
```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
python3 .lean/scripts/workflow.py --root . check
python3 .lean/scripts/model_catalog.py --root . check
python3 -m unittest discover -s .lean/tests -p 'test_skill_pack.py'
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/check_commit_attribution.py --root .
python3 .lean/tests/run_tests.py --shards 6 test-hooks.sh test_gate_integrity.py
```
<!-- gate:end -->
<!-- trusted-control-refs: refs/remotes/origin/develop refs/remotes/origin/main -->

Gate controls that equal `origin/develop` or `origin/main` are accepted automatically; see `policy/QUALITY.md`.

## High-risk areas

- `.claude/hooks/` and `.claude/settings.json`: run on every turn and control permissions; a bug can block all work or widen access.
- `.lean/scripts/gate_lock.py`: controls gate serialization and must be reviewed with the runner.
- `.lean/scripts/contract_guard.py`: PreToolUse contract guard for both providers; a bug can block every write or let writes through undeclared.
- `.lean/scripts/gate_mode.py`, `.codex/hooks.json` and `.codex/hooks/`: shared gate policy and Codex lifecycle adapter.
- `.lean/policy/`: changes alter behavior for every downstream project on upgrade.

## Development rules

- Provider parity: every workflow feature, hook and enforcement must work for both Claude and Codex with equivalent outcomes. Where a runtime cannot support part of it, record the gap explicitly in the feature's documentation and tests; never ship Claude-only or Codex-only behavior silently. Changes include tests for both providers' adapters.

## Documentation routes

Select only the route needed, then follow affected dependencies; the list is not a read-all checklist.

- User-facing setup, modes and commands -> `README.md`, then the relevant linked guide
- Tooling implementation, environment limitations and detailed test coverage -> `docs/workflow-development.md`
- Shared rules and context selection -> `.lean/README.md`, then its relevant policy route
- Imports, ownership and upgrades -> `.lean/CUSTOMIZING.md`
- Version history and migrations -> `.lean/CHANGELOG.md`
- Contribution checks -> `CONTRIBUTING.md`
