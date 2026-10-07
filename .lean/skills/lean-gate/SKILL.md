---
name: lean-gate
description: Run the Lean Workflow Quality Gate and report whether the task can be DONE. Use before declaring a task complete, or when the user asks whether work is finished.
user-invocable: false
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

For an active submodule target, resolve `python3 .lean/scripts/submodule.py context`; read the returned `project_file` and run `python3 .lean/scripts/submodule.py gate`. This executes application checks in `project_root` and blocks on undefined/failed checks. Also run Lean's own PROJECT gate for workflow changes, with explicit `--root <workflow_root>` on its workflow/catalog checks. Do not substitute a passing Lean self-check for target validation; workset records belong to `record_root`.

1. Read `.lean/policy/QUALITY.md`.
2. Run `bash .lean/scripts/quality-gate.sh --root <workflow_root>` to execute PROJECT checks. Reuse deterministic validation for the unchanged shipping state; do not repeat it merely to report completion. Missing/empty checks block: run applicable checks and configure an accepted gate before claiming it passed. Direct calls always run; caching requires explicit `--cache-tree` in Claude. For HIGH depth, also run `python3 .lean/scripts/gate_evidence.py --root <workflow_root> check-review --contract '<exact contract line>'` after review. Local control drift requires recorded, already matching user approval; never accept drift merely to pass.
3. Check every Quality Gate condition in `.lean/policy/QUALITY.md`: acceptance evidence, deterministic validation, tests for behavior changes, review depth and its coverage of the shipping delta, no unreported skips, and mode-specific tracker/queue synchronization.
4. Output the Result Contract from `.lean/policy/CONTRACTS.md`. Status is `DONE` only if every condition holds with evidence; otherwise `BLOCKED` or `FAILED` with what is missing.
