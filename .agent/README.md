# Agent policy router

Lean Workflow Baseline 1.1.0. See `CHANGELOG.md` for changes and upgrading.

This directory holds operating rules for agents. It is not application structure and prescribes no language, framework, layout, package manager, database, or deployment model.

Do **not** load every file by default. A trivial task (see `WORKFLOW.md`) needs none of them.

## Read when needed

- Running project commands or editing an unfamiliar area -> `PROJECT.md`
- Non-trivial task: planning, states, execution mode -> `WORKFLOW.md`
- Setting quality/budget/risk or reporting results -> `CONTRACTS.md`
- Behavior change, bug fix, or tests -> `TESTING.md`
- Quality floor, completion evidence -> `QUALITY.md`
- Medium/high-risk review or reviewer role -> `REVIEW.md`
- Model choice, subagent model, escalation -> `MODELS.md`
- Unfamiliar area or context expansion -> `CONTEXT.md`
- Tool selection, subagents, parallelism -> `TOOLS.md`
- Failure, retry, or rework -> `RECOVERY.md`

## Routing rule

Start with the shallowest sufficient context. Read deeper only when the task, evidence, or dependency requires it. Routes are preferred, not mandatory detours when the exact target is already known.
