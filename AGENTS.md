# Agent Instructions

Lean Workflow Baseline 4.1.0. This file is the canonical contract for all coding agents.

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
- For a submodule target, start from Lean and run `python3 .lean/scripts/submodule.py context`. Read its `project_file` and target instructions. Workflow rules/tools stay in `workflow_root`; project-owned PROJECT/config/catalog, trackers, queue and runtime state stay in `record_root`. Application code, commands and Git operations use `project_root`. Default workflow/catalog CLI commands select target records; `--root` overrides selection. Run the target gate explicitly in Codex and retain Lean's own gate for workflow changes. Never install workflow files into the target or silently fall back when its context is invalid.
- `standard` uses session evidence; `tracker` adds workset documents; `full` adds queue claims. These modes do not select a model, execution strategy, quality floor or review depth.
- `direct` is the portable default. `delegated` makes the active agent the Controller: delegate bounded implementation/investigation, including small work, to one capable worker. The Controller owns planning, accepted scope, synchronization, validation, integration, review coordination and final reporting. If required delegation is unavailable, report BLOCKED. Follow `.lean/skills/lean-multi-agent/SKILL.md`.
- Concurrent workers require independent tasks, exclusive file ownership and explicit parallel/multi-agent user intent. Independent HIGH review is required regardless of implementation routing.
- Select the least costly capable model and supported effort by `.lean/policy/MODELS.md`. Before premium dispatch, record outcome, material constraints and concrete evidence that a cheaper available option is insufficient. A risk label, model preference or complexity claim alone is not evidence. Do not authorize paid usage implicitly. Record requested and reported settings honestly.
- For HIGH review depth, use an independent reviewer: Claude's `reviewer` subagent (`.claude/agents/reviewer.md`), or a Codex subagent/fresh session. Give it `.lean/roles/reviewer.md`, the Task Contract and shipping diff without the author's reasoning. Select model and effort by `.lean/policy/MODELS.md`; report BLOCKED when required independence is unavailable.
- Claude's SessionStart/Stop hooks live in `.claude/settings.json`. Codex discovers shared skills through `.agents/skills/` links and runs the shared Quality Gate explicitly; Claude settings are not Codex hooks or permissions.
- If the Quality Gate fails, fix only failures caused by this task. Report pre-existing, unavailable-tool or out-of-scope failures as BLOCKED with evidence; do not edit tests or the gate merely to pass.

## Workflow procedures

Core procedures live under `.lean/skills/`, exposed by per-skill links in `.claude/skills/` and `.agents/skills/`: `lean-init`, `lean-scope`, `lean-research`, `lean-grill`, `lean-task`, `lean-review`, `lean-gate`, `lean-multi-agent`, `lean-skill-effort`. All discovered Lean skills are user-invocable and remain available to the agent. Resolve procedure intensity using `.lean/policy/SKILL-EFFORT.md`; project settings default to standard when absent and never change model reasoning effort. Optional maintenance procedures and discovery controls are documented in `.lean/OPTIONAL.md`. Canonical resources remain available for explicit use.
Use accepted scope and decisions; routine execution within approved scope needs no repeated approval. Scope changes and unresolved material decisions need the user's input before dependent work.

## Policy router

@.lean/README.md

## Project additions

<!-- Project-specific instructions go below this line. Preserve this section during upgrades. -->
