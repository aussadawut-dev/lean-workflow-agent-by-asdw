---
name: lean-task
description: Start a non-trivial task under Lean Workflow. States the Task Contract (risk, quality, acceptance) before any change, then works through test, validation, review, and the Quality Gate. Use when the user starts a feature, bug fix, refactor, or other non-trivial change.
argument-hint: <task description>
---

Task: $ARGUMENTS

1. The first line of your reply is the contract line from `CLAUDE.md`, before any tool call that changes files. Infer values; do not ask the user unless the goal itself is ambiguous. If unsure of risk, read `.lean/policy/CONTRACTS.md`.
2. Read `.lean/PROJECT.md` for commands.
3. Work, then test:
   - Behavior change: add tests for it and its edges.
   - Bug fix: write the regression test first, run it and show the failure, then fix and show it passes.
4. Run the Quality Gate commands from `.lean/PROJECT.md`.
5. Review at the deeper of risk and quality. `HIGH` depth: use the `reviewer` subagent, spawned on the strongest model available to this session -- it is `model: inherit`, so otherwise the `HIGH` rule in `.lean/policy/MODELS.md` never fires. If the reviewer did not run on the strongest model available, say so in the result. Read `.lean/policy/REVIEW.md` only for `MEDIUM` or `HIGH`.
6. Finish with the Result Contract: Status, Changes, Evidence, Not verified, Follow-ups.
