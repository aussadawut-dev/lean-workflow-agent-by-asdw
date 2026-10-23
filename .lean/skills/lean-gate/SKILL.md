---
name: lean-gate
description: Run the Quality Gate and report whether the task can be DONE. Use before declaring completion or when asked if work is finished.
user-invocable: true
argument-hint: "[task or workset]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

For an active submodule target, resolve `python3 .lean/scripts/submodule.py context`; read the returned `project_file` and run `python3 .lean/scripts/submodule.py gate`. This executes application checks in `project_root` and blocks on undefined/failed checks. Also run Lean's own PROJECT gate for workflow changes, with explicit `--root <workflow_root>` on its workflow/catalog checks. Do not substitute a passing Lean self-check for target validation; workset records belong to `record_root`.

1. Read `.lean/policy/QUALITY.md`.
2. Run `bash .lean/scripts/quality-gate.sh --root <workflow_root>` to execute PROJECT checks, adding `--cache-tree` when the project's Stop commands use it (`.claude/settings.json`, `.codex/hooks.json`) so the next Stop on the unchanged shipping state reuses this pass instead of running the checks again (in `manual` or `manual_fixloop` mode, always get user authorization before starting the full gate unless `/lean-gate` was explicitly invoked or matching workset/batch approval already exists; in `auto_fixloop` or `manual_fixloop` mode, once the gate runs, auto-loop over actionable code, test and lint failures and re-run until the gate passes without asking between rounds, stopping only for genuine requirement/design questions or missing tools). Reuse deterministic validation for the unchanged shipping state; do not repeat it merely to report completion. Missing/empty checks block: run applicable checks and configure an accepted gate before claiming it passed. Without `--cache-tree`, direct calls always run. For HIGH depth, also run `python3 .lean/scripts/gate_evidence.py --root <workflow_root> check-review --contract '<exact contract line>'` after review. Local control drift requires recorded, already matching user approval; never accept drift merely to pass.
3. Check every Quality Gate condition in `.lean/policy/QUALITY.md`: acceptance evidence, deterministic validation, tests for behavior changes, review depth and its coverage of the shipping delta, no unreported skips, and mode-specific tracker/queue synchronization.
4. Output the Result Contract from `.lean/policy/CONTRACTS.md`. Status is `DONE` only if every condition holds with evidence; otherwise `BLOCKED` or `FAILED` with what is missing.
