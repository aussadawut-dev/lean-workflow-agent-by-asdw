# Developing Lean

[Back to README](../README.md)

## Layout

| Path | Contents |
|---|---|
| `.lean/bin/lean` | the only entry point; adds `.lean/` to the import path and calls `lean.cli.main` |
| `.lean/lean/cli.py` | argument parsing and dispatch only |
| `.lean/lean/guard.py` | Task Contract parsing, transcript binding, write detection, receipt protection |
| `.lean/lean/evidence.py` | shipping state, review receipts, gate controls, High-risk paths |
| `.lean/lean/gate.py` | gate runner, lock, cache, refusal counting, gate mode |
| `.lean/lean/hooks.py` | Claude and Codex lifecycle adapters |
| `.lean/lean/records.py` | modes, trackers, queue leases, downgrades, context |
| `.lean/lean/progress.py` | progress state and bar rendering |
| `.lean/lean/activity.py` | timed activity log behind `lean log` |
| `.lean/lean/models.py`, `spawn.py` | model list, spawn planning, headless runs |
| `.lean/lean/testsel.py` | test categories, impact selection, parallel runner |
| `.lean/lean/structure.py`, `attribution.py`, `effort.py`, `update.py` | lint, commit attribution, procedure intensity, updates |
| `.lean/tests/{unit,hooks,e2e}/` | tests; `support.py` installs the CLI into disposable repositories |
| `.lean/tests/impact.json` | which tests a changed path can affect |

Standard library only; Python 3.9 is the floor (CI runs 3.9 and the latest release on Linux and macOS). Commands that only read must not create files in the checkout; the entry point disables bytecode caches.

## Checks

```sh
python3 .lean/bin/lean lint
python3 .lean/bin/lean test --changed --list   # what a change would run
python3 .lean/bin/lean test --changed
python3 .lean/bin/lean test --all              # before a release; CI runs this
python3 .lean/bin/lean gate run
```

When you add a test file, add a rule for it in `impact.json` (or it runs only in full runs) and list it in `.lean/assets.json`. Lint fails when a workflow-owned file is missing from the registry; `lean lint --write-registry` regenerates it from the Git-visible workflow files; review the diff.

## Releasing

Bump the version in `AGENTS.md`, `.lean/README.md`, `.lean/lean/__init__.py` and a new `.lean/CHANGELOG.md` entry (lint checks they agree), run `lean test --all` and the gate, finish the HIGH review, then tag `vMAJOR.MINOR.PATCH`. `lean update` picks the highest stable tag.

## Spawning tests

`e2e/test_spawn_run.py` replaces the provider CLI with a stub script, so it needs no subscription and spends no quota. To try a real provider by hand: `lean spawn run --tasks .lean/templates/tasks.json --provider agy --timeout 300` in a scratch clone. agy 1.0.6 was reported to hang in print mode without a TTY; `--print-timeout` and the runner's own timeout bound that.
