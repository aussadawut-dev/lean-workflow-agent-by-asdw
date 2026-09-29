---
name: lean-task
description: Start a non-trivial task under Lean Workflow. States the Task Contract (goal, scope, quality, budget, risk, acceptance) before any change. Use when the user starts a feature, bug fix, refactor, or other non-trivial change.
argument-hint: <task description>
---

Task: $ARGUMENTS

1. Read `.agent/policy/CONTRACTS.md` and `.agent/policy/WORKFLOW.md`. Read `.agent/PROJECT.md` if you will run commands or touch unfamiliar areas.
2. If the task is trivial (per `.agent/policy/WORKFLOW.md`), say so in one line and just do it with evidence.
3. Otherwise write the Task Contract in a compact block: Goal, Scope, Quality, Budget, Risk, Acceptance. Use the defaults and risk inference from `.agent/policy/CONTRACTS.md`; do not ask the user for values unless the goal itself is ambiguous.
4. Proceed through the workflow: context, work, test, validate, review, Quality Gate. Load `.agent/policy/TESTING.md`, `.agent/policy/REVIEW.md`, and other policy files only when you reach the step that needs them.
5. Finish with the Result Contract.
