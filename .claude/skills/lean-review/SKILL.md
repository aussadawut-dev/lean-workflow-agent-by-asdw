---
name: lean-review
description: Review the current change at the depth Lean Workflow requires. Uses the reviewer subagent for HIGH depth. Use after implementation and deterministic validation, or when the user asks for a review.
argument-hint: [diff range or scope]
---

Scope: $ARGUMENTS (default: uncommitted changes)

1. Read `.lean/policy/REVIEW.md`.
2. Confirm deterministic validation already passed. If it has not run, run the Quality Gate commands from `.lean/PROJECT.md` first.
3. Determine depth: the deeper of risk and quality floor from the Task Contract. If there is no contract, infer risk per `.lean/policy/CONTRACTS.md`.
4. Review:
   - `LOW` — self-check against acceptance criteria.
   - `MEDIUM` — focused diff review yourself.
   - `HIGH` — spawn the `reviewer` subagent with the Task Contract and diff range only. Do not
     pass your reasoning. Spawn it on the strongest model available to this session: the agent is
     `model: inherit`, so without that the reviewer is only as strong as the session that wrote the
     change, which is what `.lean/policy/MODELS.md` rules out for `HIGH`. If you cannot choose the
     model, let it inherit and name in the result which model reviewed and that it was not the
     strongest available.
5. Act on the verdict under `Rounds` in `.lean/policy/REVIEW.md`, which bounds both branches:
   - `PASS` — the review is over; anything applied after it is a new contract.
   - `REWORK` — fix the findings, re-run validation, review again with delta context only. It caps
     the rounds on one contract and says when the result is `BLOCKED` rather than `DONE`.
6. Report the verdict and findings in the Review Contract format, and say which round this was: the
   count lives nowhere else, so a later session cannot recover it.
