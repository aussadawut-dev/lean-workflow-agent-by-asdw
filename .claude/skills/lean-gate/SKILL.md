---
name: lean-gate
description: Run the Lean Workflow Quality Gate and report whether the task can be DONE. Use before declaring a task complete, or when the user asks whether work is finished.
user-invocable: false
---

For an active submodule target, resolve `python3 .lean/scripts/submodule.py context`; read the returned `project_file` and run `python3 .lean/scripts/submodule.py gate`. This executes application checks in `project_root` and blocks on undefined/failed checks. Also run Lean's own PROJECT gate for workflow changes, with explicit `--root <workflow_root>` on its workflow/catalog checks. Do not substitute a passing Lean self-check for target validation; workset records belong to `record_root`.

1. Read `.lean/policy/QUALITY.md`.
2. Run the Quality Gate commands between the `gate:start` and `gate:end` markers in `.lean/PROJECT.md`. If none are defined, run whatever validation the task needs and say the gate is undefined.
3. Check every Quality Gate condition in `.lean/policy/QUALITY.md`: acceptance evidence, deterministic validation, tests for behavior changes, review depth and its coverage of the shipping delta, no unreported skips, and mode-specific tracker/queue synchronization.
4. Output the Result Contract from `.lean/policy/CONTRACTS.md`. Status is `DONE` only if every condition holds with evidence; otherwise `BLOCKED` or `FAILED` with what is missing.
