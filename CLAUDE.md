# Claude Instructions

This repository uses Lean Workflow Baseline #1. This file is the canonical agent contract.

## Core rules

- Establish the task contract before non-trivial work.
- Use the smallest sufficient context.
- Behavior changes require meaningful test evidence.
- Run deterministic validation before semantic review.
- Review depth is the deeper of risk and quality floor.
- Never silently downgrade the requested quality floor.
- Do not declare DONE without evidence.
- Do not spend additional model effort without a useful reason.

## Claude guidance

- Prefer direct execution for simple or tightly coupled work.
- Use subagents only for genuinely independent parallel work or isolated review/research.
- Do not raise thinking/effort merely because a task is long; follow `.agent/MODELS.md`.
- A `Stop` hook runs the Quality Gate commands in `.agent/PROJECT.md`. If it blocks, fix the failure or report `BLOCKED`/`FAILED`. Never edit the gate to get past it unless the user asks.

## Policy router

@.agent/README.md

## Project additions

<!-- Project-specific Claude instructions go below this line. Workflow upgrades replace everything above it. -->
