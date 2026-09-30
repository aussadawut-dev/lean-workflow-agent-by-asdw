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
   - `HIGH` — spawn the `reviewer` subagent with the Task Contract and diff range only. Do not pass your reasoning.
5. On `REWORK`, fix the findings, re-run validation, and review again with delta context only.
   Stop after the second `REWORK`: report what is left and let the user decide on a third.
   A `PASS` ends the review. Apply what is cheap and clearly right, but do not open a round
   to check it. New work that arrives mid-cycle is its own contract, not an addition to this one.
6. Report the verdict and findings in the Review Contract format.
