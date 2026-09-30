---
name: lean-init
description: Fill in .lean/PROJECT.md from the real repository (purpose, architecture, commands, important paths, Quality Gate). Use when PROJECT.md still says "Not defined", after adding the workflow to an existing project, or when the project's commands or structure changed.
---

Update `.lean/PROJECT.md` to match the repository as it is now.

1. Read `.lean/PROJECT.md`.
2. Inspect the repository shallowly: root files, manifests and build files (whatever exists, e.g. `package.json`, `go.mod`, `pyproject.toml`, `Cargo.toml`, `Makefile`), CI config, top-level directories, existing READMEs.
3. Fill each section only with facts you found. Leave "Not defined" where the repository has no convention. Do not invent architecture or commands.
4. For each command you record, run it once if it is safe and fast, and note whether it works.
5. Put the fast, deterministic checks that must pass before a task is DONE (typically lint, typecheck, unit tests) between the `gate:start` and `gate:end` markers, one per line. Leave the block empty if none exist yet.
   Every gate command must exit non-zero when the check fails. Some tools only print problems and exit 0; wrap them, e.g. `test -z "$(gofmt -l .)"` instead of `gofmt -l .`. Verify by running the command once.
6. Add area READMEs you found under Documentation routes.
7. Show the user a short summary of what changed and what is still undefined.

$ARGUMENTS
