# Claude Instructions

This repository uses Lean Workflow Baseline #1. This file is the canonical agent contract.

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

## Claude guidance

- Prefer direct execution for simple or tightly coupled work.
- Use subagents only for genuinely independent parallel work or isolated review/research.
- Do not raise thinking/effort merely because a task is long; follow `.lean/policy/MODELS.md`.
- A `Stop` hook runs the Quality Gate commands in `.lean/PROJECT.md`. If it blocks, fix the failure only if your change caused it. If the failure was already there or is outside the task, do not touch it: report `BLOCKED` and ask. Never edit the gate or tests to get past it unless the user asks.
- For `HIGH` review depth, use the `reviewer` subagent (`.claude/agents/reviewer.md`), spawned on the strongest model available: it is `model: inherit`, so otherwise the reviewer is only as strong as the session that wrote the change. If you cannot choose the model, say which model reviewed in the result.
- Workflow skills: `/lean-init` (fill `PROJECT.md`), `/lean-task` (Task Contract), `/lean-review` (risk-based review), `/lean-gate` (Quality Gate and Result Contract).

## Policy router

@.lean/README.md

## Project additions

<!-- Project-specific Claude instructions go below this line. Workflow upgrades replace everything above it. -->
