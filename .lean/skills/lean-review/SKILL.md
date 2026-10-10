---
name: lean-review
description: Review the current change at the depth Lean Workflow requires. Uses an independent reviewer for HIGH depth. Use after implementation and deterministic validation, or when the user asks for a review.
user-invocable: true
argument-hint: "[diff or scope]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

For an independent reviewer on either runtime, supply `.lean/roles/reviewer.md`, the Task Contract and shipping diff without author reasoning.

Scope: $ARGUMENTS (default: uncommitted changes)

1. Read `.lean/policy/REVIEW.md`.
2. Confirm deterministic validation already passed. If it has not run, run the Quality Gate commands from `.lean/PROJECT.md` first.
3. Determine depth: the deeper of risk and quality floor from the Task Contract. If there is no contract, infer risk per `.lean/policy/CONTRACTS.md`.
4. Review:
   - `LOW` — self-check against acceptance criteria.
   - `MEDIUM` — focused diff review yourself.
   - `HIGH` — use an independent reviewer: Claude's `reviewer` subagent, or a Codex subagent or
     fresh session. Give it the Task Contract and diff range only, without your reasoning. Select
     its model and effort by `.lean/policy/MODELS.md`; `model: inherit` is Claude's portable
     default. If no independent reviewer is available, follow `.lean/policy/REVIEW.md` and report
     `BLOCKED`.
5. Act on the verdict under `Rounds` in `.lean/policy/REVIEW.md`, which bounds both branches:
   - `PASS` — the review is over; anything applied after it is a new contract.
   - `REWORK` — fix the findings, re-run validation, review again with delta context only. It caps
     the rounds on one contract and says when the result is `BLOCKED` rather than `DONE`.
6. Have the HIGH reviewer record its verdict through `.lean/scripts/gate_evidence.py record-review` as specified in `REVIEW.md`. Check the receipt against the shipping state and exact contract; later edits invalidate it. Report the Review Contract, scope and round. The receipt records coverage and the reported identity, not proof of organizational independence.
