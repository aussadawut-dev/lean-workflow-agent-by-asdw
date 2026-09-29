---
name: lean-review
description: Review the current change at the depth Lean Workflow requires. Uses the reviewer subagent for HIGH depth. Use after implementation and deterministic validation, or when the user asks for a review.
argument-hint: [diff range or scope]
---

Scope: $ARGUMENTS (default: uncommitted changes)

1. Read `.agent/REVIEW.md`.
2. Confirm deterministic validation already passed. If it has not run, run the Quality Gate commands from `.agent/PROJECT.md` first.
3. Determine depth: the deeper of risk and quality floor from the Task Contract. If there is no contract, infer risk per `.agent/CONTRACTS.md`.
4. Review:
   - `LOW` — self-check against acceptance criteria.
   - `MEDIUM` — focused diff review yourself.
   - `HIGH` — spawn the `reviewer` subagent with the Task Contract and diff range only. Do not pass your reasoning.
5. On `REWORK`, fix the findings, re-run validation, and review again with delta context only.
6. Report the verdict and findings in the Review Contract format.
