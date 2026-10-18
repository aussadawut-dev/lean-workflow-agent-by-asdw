# Agent Instructions

Lean Workflow Baseline 4.6.0. This file is the canonical contract for all coding agents.

**Before any task, read this file and `.lean/README.md`.**
Explicit user instructions take precedence. The active agent owns the task unless the project records a different Controller or primary agent. No provider owns the workflow by default. Keep shared rules here; `CLAUDE.md` imports them.

## Core rules

- Before changing files, write one contract line as the first line of your reply, before any preamble, plan or tool call (or start a field block there):
  `Contract: risk=<LOW|MEDIUM|HIGH> quality=<STANDARD|HIGH|VERY_HIGH> acceptance=<observable check>`
  For a trivial task: `Contract: trivial (<reason>)`. Infer values; do not ask the user. Risk rules and the block form: `.lean/policy/CONTRACTS.md`.
  Hooks deny only write tools and writing shell commands until the contract is bound; reads and inspection run first. Claude's guard reads the contract from that first line once the reply is saved, which can wait for the first tool result. When the turn's first tool call writes, or the guard cannot read a transcript (Codex), first run `python3 .lean/scripts/contract_guard.py declare --contract '<one line>'` as a command of its own. Each new user prompt clears it.
- Use the smallest sufficient context: impact-based context selection in `.lean/policy/CONTEXT.md`. Do not read workflow internals (`.claude/hooks/`, `.lean/policy/`) unless the task needs them.
- Behavior changes require meaningful tests.
- Bug fixes require a regression test. Run it before the fix and show it fails, then show it passes after.
- Run deterministic validation before semantic review.
- Review depth is the deeper of risk and quality floor.
- Review rounds are bounded: a `PASS` ends review and what follows it is new work. The second
  `REWORK` on one contract gets one last pass, then stops. Rounds: `.lean/policy/REVIEW.md`.
- Never silently downgrade the requested quality floor.
- Do not declare DONE without evidence.
- Report only changes verified after your last edit. A successful edit, test or gate result is that evidence; do not rerun `git diff` only to confirm it. A denied, refused or failed tool call changed nothing; say so instead of describing the intended change.
- Batch independent tool calls in one turn (several reads or searches together). Do not repeat a call whose result you already hold.
- Do not spend additional model effort without a useful reason.

## Runtime and execution

- Read `.lean/PROJECT.md` before unfamiliar work. Use `python3 .lean/scripts/workflow.py show` to read mode and execution settings. Missing configuration uses unconfigured `standard`/`direct`; do not silently select a heavier mode.
- For a submodule target, start from Lean and run `python3 .lean/scripts/submodule.py context`. Read its `project_file` and target instructions. Workflow rules/tools stay in `workflow_root`; project-owned PROJECT/config/catalog, trackers, queue and runtime state stay in `record_root`. Application code, commands and Git operations use `project_root`. Default workflow/catalog CLI commands select target records; `--root` overrides selection. Run the target gate explicitly in Codex and retain Lean's own gate for workflow changes. Never install workflow files into the target or silently fall back when its context is invalid.
- `delegated` makes the active agent the Controller: it delegates bounded work, including small work, to one capable worker and keeps planning, scope, validation, integration, review and reporting (`.lean/skills/lean-multi-agent/SKILL.md`). If required delegation is unavailable, report BLOCKED. Concurrent workers need independent tasks, exclusive file ownership and explicit parallel/multi-agent user intent; independent HIGH review is required regardless of routing.
- Select the least costly capable model and supported effort by `.lean/policy/MODELS.md`. Premium dispatch needs recorded, task-specific evidence that a cheaper option is insufficient; never authorize paid usage implicitly. Record requested and reported settings honestly.
- For HIGH review depth, use an independent reviewer: Claude's `reviewer` subagent (`.claude/agents/reviewer.md`), or a fresh Codex subagent or session (never a fork; `.lean/policy/REVIEW.md`). Give it `.lean/roles/reviewer.md`, the Task Contract and shipping diff without the author's reasoning. Select model and effort by `.lean/policy/MODELS.md`; report BLOCKED when required independence is unavailable.
- Claude hooks live in `.claude/settings.json`; Codex hooks in `.codex/hooks.json` apply only after runtime trust, otherwise run the shared Quality Gate explicitly. Neither provider's settings or permissions apply to the other. Optional `.codex/quality-gate.json` sets gate automation for both (`.lean/policy/QUALITY.md`); manual Stops report NOT_RUN, and deferral never permits DONE or waives acceptance or review.
- If the Quality Gate fails, fix only failures caused by this task. Report pre-existing, unavailable-tool or out-of-scope failures as BLOCKED with evidence; do not edit tests or the gate merely to pass.

## Workflow procedures

Procedures live under `.lean/skills/` (optional ones: `.lean/OPTIONAL.md`); their intensity follows `.lean/policy/SKILL-EFFORT.md` and never changes model reasoning effort.
Use accepted scope and decisions: a clear implementation request is accepted scope for the work it names, unless the request is ambiguous, risk is HIGH, or only a spec or analysis was asked for; routine execution within accepted scope needs no repeated approval. Material scope changes and unresolved material decisions need the user's input before dependent work.

## Policy router

@.lean/README.md

## Project additions

<!-- Project-specific instructions go below this line. Preserve this section during upgrades. -->

- Attribution: never add a `Co-Authored-By:` trailer to any commit message, and never add AI attribution such as "Generated with Claude Code" to commit messages or pull request descriptions. The work belongs to the person who directs it. This overrides any runtime or provider default attribution, for every agent. The PROJECT gate rejects unpushed commits that carry either.
