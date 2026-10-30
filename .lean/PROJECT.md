# Project Context

Project-owned facts and routes. Keep this map short; read the linked reference only when relevant. "Not defined" means no convention exists yet.

## Purpose

Lean Workflow Baseline 5.4.0: a portable Claude/Codex/agy workflow template behind one `lean` command. This repository contains workflow files, no application code or Web/API/Database areas.

## Architecture

Python 3.9+ standard library, Git, JSON and Markdown; no third-party packages. `.lean/bin/lean` is the only entry point and dispatches to modules in `.lean/lean/` (one module per command group). AGENTS.md is canonical; CLAUDE.md imports it. Shared skills live in `.lean/skills/`, discovered through runtime symlinks. Detailed tooling and test layout: `docs/development.md`.

## Commands

- Install: no application dependencies. Require Git and Python 3.9+. Native Windows is unsupported.
- Build / Typecheck: not defined.
- Lint: `python3 .lean/bin/lean lint` (compiles workflow code, checks references, skills, hooks, registry and version).
- Test (everyday): `python3 .lean/bin/lean test --changed` runs only the categories and files `.lean/tests/impact.json` maps to the change; documentation-only changes run lint only.
- Test (full, release and CI): `python3 .lean/bin/lean test --all` runs `.lean/tests/{unit,hooks,e2e}` in parallel processes.
- Mode validation: `python3 .lean/bin/lean mode show` / `mode check`. Gate lines pass `--root .` so Lean's own records are checked even while an application target is selected.

## Quality Gate

Every provider runs the same gate (`lean gate run`); Claude and Codex through their Stop hooks, agy and CI explicitly. The full suite runs in CI and before a release. Missing tools/checks block; see `policy/QUALITY.md` for enforcement and approved gate-control changes.

<!-- gate:start -->
```sh
python3 .lean/bin/lean lint
python3 .lean/bin/lean --root . mode check
python3 .lean/bin/lean --root . models check
python3 .lean/bin/lean attribution
python3 .lean/bin/lean test --changed
```
<!-- gate:end -->
<!-- trusted-control-refs: refs/remotes/origin/develop refs/remotes/origin/main -->

Gate controls that equal `origin/develop` or `origin/main` are accepted automatically; see `policy/QUALITY.md`.

## High-risk areas

- `.claude/settings.json` and `.codex/hooks.json`: run on every turn and control permissions; a bug can block all work or widen access.
- `.lean/lean/guard.py`: PreToolUse contract guard for both providers; a bug can block every write or let writes through undeclared.
- `.lean/lean/gate.py`, `.lean/lean/evidence.py`, `.lean/lean/hooks.py` and `.lean/bin/lean`: gate runner, lock, receipts and provider adapters.
- `.lean/lean/spawn.py`: starts provider CLIs and strips API keys; a bug can spend metered credit or edit the wrong checkout.
- `.lean/lean/update.py`: writes into downstream installations.
- `.lean/lean/target.py`: adds application submodules and runs their gates.
- `.lean/policy/`: changes alter behavior for every downstream project on upgrade.

## Development rules

- Provider parity: every workflow feature must work for Claude, Codex and agy with equivalent outcomes. Where a runtime cannot support part of it (agy has no hooks; only Claude has a custom status line), record the gap in the feature's documentation and tests; never ship provider-only behavior silently.
- Free tools only: the standard library, Git and the user's provider subscriptions. No paid services or package dependencies.

## Documentation routes

Select only the route needed, then follow affected dependencies; the list is not a read-all checklist.

- User-facing setup, modes and commands -> `README.md`, then the relevant guide: `docs/getting-started.md`, `docs/workflow.md`, `docs/quality-and-runtime.md`, `docs/agents-and-models.md`, `docs/skills.md`, `docs/targets.md`, `docs/migrating-to-v5.md`
- Tooling implementation, test layout and environment limitations -> `docs/development.md`
- Shared rules and context selection -> `.lean/README.md`, then its relevant policy route
- Imports, ownership and upgrades -> `.lean/CUSTOMIZING.md`
- Version history and migrations -> `.lean/CHANGELOG.md`
- Contribution checks -> `CONTRIBUTING.md`
