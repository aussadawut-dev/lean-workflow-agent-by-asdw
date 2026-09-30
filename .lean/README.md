# Agent policy router

Lean Workflow Baseline 2.0.0. See `CHANGELOG.md` for changes and upgrading.

This directory holds the operating rules for agents and the self-checks for those rules. It is not application structure and prescribes no language, framework, layout, package manager, database, or deployment model.

## Layout

- `PROJECT.md` — owned by the project. Agents and people update it.
- `policy/` — owned by the workflow. Do not edit per project; upgrades replace it.
- `CHANGELOG.md` — workflow versions and upgrade steps.
- `scripts/`, `tests/` — self-checks for the files in here. Not your project's own checks.

Do **not** load every file by default. A trivial task (see `policy/WORKFLOW.md`) needs none of them.

## Read when needed

- Running project commands or editing an unfamiliar area -> `PROJECT.md`
- Non-trivial task: planning, states, execution mode -> `policy/WORKFLOW.md`
- Setting quality/budget/risk or reporting results -> `policy/CONTRACTS.md`
- Behavior change, bug fix, or tests -> `policy/TESTING.md`
- Quality floor, completion evidence -> `policy/QUALITY.md`
- Medium/high-risk review or reviewer role -> `policy/REVIEW.md`
- Model choice, subagent model, escalation -> `policy/MODELS.md`
- Unfamiliar area or context expansion -> `policy/CONTEXT.md`
- Tool selection, subagents, parallelism -> `policy/TOOLS.md`
- Failure, retry, or rework -> `policy/RECOVERY.md`

## Routing rule

Start with the shallowest sufficient context. Read deeper only when the task, evidence, or dependency requires it. Routes are preferred, not mandatory detours when the exact target is already known.
