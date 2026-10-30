---
name: lean-gate
description: Run the Quality Gate and report whether the task can be DONE. Use before declaring completion or when asked if work is finished.
user-invocable: true
argument-hint: "[task or workset]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md`; keep model reasoning effort separate.

1. Read `.lean/policy/QUALITY.md` and run `python3 .lean/bin/lean progress set gate`.
2. Run `python3 .lean/bin/lean gate run --contract '<exact contract line>'`, adding `--cache-tree` when the project's Stop commands use it so the next Stop on the unchanged shipping state reuses this pass. In `manual` or `manual_fixloop` mode, get user authorization before the full gate unless `/lean-gate` was invoked explicitly or matching workset/batch approval exists; in `auto_fixloop` or `manual_fixloop`, once the gate runs, auto-loop over actionable code, test and lint failures until it passes without asking between rounds, stopping only for genuine requirement/design questions or missing tools. Reuse deterministic validation for the unchanged shipping state; do not repeat it merely to report completion. For a batch of tasks, run one full gate covering every task's final state, not one per task; a suspected flaky failure gets at most 2 reruns (`QUALITY.md`). Missing or empty checks block. For HIGH depth, also run `python3 .lean/bin/lean evidence check-review --contract '<exact contract line>'` after review. Control drift needs recorded, already matching user approval (`lean gate accept-controls`) or a covering HIGH review; never accept drift merely to pass.
3. Check every Quality Gate condition: acceptance evidence, deterministic validation, tests for behavior changes, review depth and its coverage of the shipping delta, no unreported skips, and mode-specific tracker/queue synchronization. After a covering shared PASS, close the owning tracker through `lean tracker status --id TCKNNN --status DONE --contract '<exact contract line>' --evidence '<acceptance and validation evidence>'`; queue completion alone cannot close it.
4. Output the Result Contract from `.lean/policy/CONTRACTS.md` with the final progress bar. Status is `DONE` only if every condition holds with evidence (then `lean progress set done`); otherwise `BLOCKED` or `FAILED` with what is missing.
