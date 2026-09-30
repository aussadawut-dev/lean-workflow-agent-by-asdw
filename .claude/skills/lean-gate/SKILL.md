---
name: lean-gate
description: Run the Lean Workflow Quality Gate and report whether the task can be DONE. Use before declaring a task complete, or when the user asks whether work is finished.
---

1. Read `.lean/policy/QUALITY.md`.
2. Run the Quality Gate commands between the `gate:start` and `gate:end` markers in `.lean/PROJECT.md`. If none are defined, run whatever validation the task needs and say the gate is undefined.
3. Check every Quality Gate condition in `.lean/policy/QUALITY.md`: acceptance evidence, deterministic validation, tests for behavior changes, review depth and its coverage of the shipping delta, no unreported skips.
4. If `.lean/bin/mode.sh get` is `tracker` or `full`, write the Result Contract into this task's
   tracking record and set its `state` to the status you are reporting. In `full`, run
   `.lean/bin/queue.sh done <id>` only for a `DONE` status; a `BLOCKED` or `FAILED` item stays claimed,
   or is released with `release <id>` if you are stopping. See `.lean/policy/MODES.md`.
5. Output the Result Contract from `.lean/policy/CONTRACTS.md`. Status is `DONE` only if every condition holds with evidence; otherwise `BLOCKED` or `FAILED` with what is missing.
