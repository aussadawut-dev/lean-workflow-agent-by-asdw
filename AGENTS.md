# Agent Instructions

Lean Workflow Baseline 3.2.0. This file is the canonical contract for all coding agents.

**Before any task, read this file and `.lean/README.md`.**
Explicit user instructions take precedence. The active agent owns the task unless the project records a different Controller or primary agent. No provider owns the workflow by default. Keep shared rules here; `CLAUDE.md` imports them.

## Core rules

- Before changing files, write one contract line as the first line of your reply:
  `Contract: risk=<LOW|MEDIUM|HIGH> quality=<STANDARD|HIGH|VERY_HIGH> acceptance=<observable check>`
  For a trivial task: `Contract: trivial (<reason>)`. Infer values; do not ask the user. Risk rules: `.lean/policy/CONTRACTS.md`.
- Use the smallest sufficient context. Do not read workflow internals (`.claude/hooks/`, `.lean/policy/`) unless the task needs them.
- Behavior changes require meaningful tests.
- Bug fixes require a regression test. Run it before the fix and show it fails, then show it passes after.
- Run deterministic validation before semantic review.
- Review depth is the deeper of risk and quality floor.
- Review rounds are bounded: a `PASS` ends review and what follows it is new work. The second
  `REWORK` on one contract gets one last pass, then stops. Rounds: `.lean/policy/REVIEW.md`.
- Never silently downgrade the requested quality floor.
- Do not declare DONE without evidence.
- Do not spend additional model effort without a useful reason.

## Runtime and execution

- Read `.lean/PROJECT.md` before unfamiliar work. Use `python3 .lean/scripts/workflow.py show` to read mode and execution settings. Missing configuration uses unconfigured `standard`/`direct`; do not silently select a heavier mode.
- `standard` uses session evidence; `tracker` adds workset documents; `full` adds queue claims. These modes do not select a model, execution strategy, quality floor or review depth.
- `direct` is the portable default. `delegated` makes the active agent the Controller: delegate bounded implementation/investigation, including small work, to one capable worker. The Controller owns planning, accepted scope, synchronization, validation, integration, review coordination and final reporting. If required delegation is unavailable, report BLOCKED. Follow `.claude/skills/lean-multi-agent/SKILL.md`.
- Concurrent workers require independent tasks, exclusive file ownership and explicit parallel/multi-agent user intent. Independent HIGH review is required regardless of implementation routing.
- Select the least costly capable model and supported effort by `.lean/policy/MODELS.md`. Before premium dispatch, record outcome, material constraints and concrete evidence that a cheaper available option is insufficient. A risk label, model preference or complexity claim alone is not evidence. Do not authorize paid usage implicitly. Record requested and reported settings honestly.
- For HIGH review depth, use an independent reviewer: Claude's `reviewer` subagent (`.claude/agents/reviewer.md`), or a Codex subagent/fresh session. Give it the Task Contract and shipping diff without the author's reasoning. Select model and effort by `.lean/policy/MODELS.md`; report BLOCKED when required independence is unavailable.
- Claude's SessionStart/Stop hooks live in `.claude/settings.json`. Codex reads `.agents/skills/` adapters and runs the Quality Gate explicitly; Claude settings are not Codex hooks or permissions.
- If the Quality Gate fails, fix only failures caused by this task. Report pre-existing, unavailable-tool or out-of-scope failures as BLOCKED with evidence; do not edit tests or the gate merely to pass.

## Workflow procedures

Shared procedures under `.claude/skills/` have thin Codex adapters under `.agents/skills/`:
`lean-init`, `lean-scope`, `lean-research`, `lean-grill`, `lean-task`, `lean-review`, `lean-gate`, `lean-multi-agent`, `clean-queue`.
Use accepted scope and decisions; routine execution within approved scope needs no repeated approval. Scope changes and unresolved material decisions need the user's input before dependent work.

## Policy router

@.lean/README.md

## Project additions

<!-- Project-specific instructions go below this line. Preserve this section during upgrades. -->
