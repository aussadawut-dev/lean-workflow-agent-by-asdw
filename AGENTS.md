# Agent Instructions

Lean Workflow Baseline 5.2.0. This file is the canonical contract for all coding agents (Claude, Codex, agy).

**Before any task, read this file and `.lean/README.md`.** In Claude, both are already loaded through the `CLAUDE.md` imports; do not read them again.
Explicit user instructions take precedence. The active agent owns the task unless the project records a different Controller or primary agent; no provider owns the workflow by default. Keep shared rules here. Every workflow command is `python3 .lean/bin/lean <command>` (`lean --help`).

## Core rules

- Before changing files, write one contract line as the first line of your reply, before any preamble, plan or tool call (or start a field block there):
  `Contract: risk=<LOW|MEDIUM|HIGH> quality=<STANDARD|HIGH|VERY_HIGH> acceptance=<observable check>`
  For a trivial task: `Contract: trivial (<reason>)`. Infer values; do not ask the user. Risk rules and the block form: `.lean/policy/CONTRACTS.md`.
  Hooks deny only write tools and writing shell commands until the contract is bound; reads and inspection run first. Claude's guard reads the contract from that first line once the reply is saved, which can wait for the first tool result, so in Claude run `declare` only when the turn's first tool call writes, to replace a bound contract, or after a write was denied. Where the guard cannot read a transcript (Codex, agy), first run `python3 .lean/bin/lean contract declare --contract '<one line>'` as its own command. A new user prompt clears the contract; in Claude, a prompt typed mid-work keeps it, so redeclare only if it changes the task.
- Progress: on entering each phase run `python3 .lean/bin/lean progress set <phase> [--done N --total M] [--task '<title>']` and put the bar it prints in your reply (`.lean/policy/WORKFLOW.md`).
- Use the smallest sufficient context (`.lean/policy/CONTEXT.md`). Skip workflow internals (`.lean/lean/`, `.lean/policy/`) unless the task needs them.
- Behavior changes require meaningful tests; while working run only those a change can affect (`lean test --changed`; `.lean/policy/TESTING.md`). Bug fixes require a regression test: show it fails before the fix and passes after.
- Run deterministic validation before semantic review. Review depth is the deeper of risk and quality floor. Never silently downgrade the requested quality floor.
- Review rounds are bounded: a `PASS` ends review and what follows is new work. The second `REWORK` on one contract gets one last pass, then stops (`.lean/policy/REVIEW.md`).
- Do not declare DONE without evidence. Report only changes verified after your last edit; a successful edit, test or gate result is that evidence, so do not rerun `git diff` to confirm it. A denied, refused or failed tool call changed nothing; say so instead of describing the intended change.
- Batch independent tool calls; do not repeat a call whose result you hold. Spend no extra model effort without reason.

## Runtime and execution

- Read `.lean/PROJECT.md` before unfamiliar work. `python3 .lean/bin/lean mode show` reads mode and execution; missing configuration is unconfigured `standard`/`direct`, never silently select a heavier mode.
- Application target (submodule under `targets/`): start from Lean, run `python3 .lean/bin/lean target context`, read its `project_file` and target instructions. Workflow rules and tools stay in `workflow_root`; PROJECT, config, trackers, queue and runtime state in `record_root`; application code, commands and Git use `project_root`. `lean mode|tracker|queue|effort|models` select the target's records by default; `--root` overrides. Run the target gate explicitly where hooks do not; keep Lean's gate for workflow changes. Never install workflow files into the target or fall back when its context is invalid (`.lean/skills/lean-target/SKILL.md`).
- Spawning follows `.lean/policy/MODELS.md` and `.lean/models.json` (`lean models`): at most `max_agents` (default 1) at a time, sized 3S, 2S, S, M, L, XL, 2XL or 3XL, only when spawning costs less than finishing here. `/lean-agents` alone spawns one agent per parallel-capable task; `/lean-agents <model> xN` runs up to N at once on that model. Pass the sized model and effort wherever the spawn tool accepts them, record requested and reported settings, never bare `inherited/inherited`. `lean spawn run` removes metered API keys so spawned CLIs use the subscription login.
- `delegated` makes the active agent the Controller: it delegates bounded work, even small, to one capable worker and keeps planning, scope, validation, integration, review and reporting (`.lean/skills/lean-agents/SKILL.md`). If required delegation is unavailable, report BLOCKED. Concurrent workers need independent tasks and exclusive file ownership.
- For HIGH review depth, use an independent reviewer: Claude's `reviewer` subagent (`.claude/agents/reviewer.md`), or a fresh Codex or agy subagent or session (never a fork; `.lean/policy/REVIEW.md`). Give it `.lean/roles/reviewer.md`, the Task Contract and the shipping diff, not the author's reasoning. Select model and effort by `.lean/policy/MODELS.md`; report BLOCKED when required independence is unavailable.
- Hooks: Claude `.claude/settings.json`; Codex `.codex/hooks.json` (only after runtime trust); agy has none, so run `lean gate run` explicitly. Provider settings do not cross providers. Optional `.lean/gate.json` sets gate automation (`auto|manual|auto_fixloop|manual_fixloop`, `lean gate mode`) for every provider. `manual` modes report NOT_RUN at Stop and need user authorization before a full gate run; deferral never permits DONE or waives acceptance or review (`.lean/policy/QUALITY.md`).
- If the Quality Gate fails in `auto` or `manual` mode, fix only failures caused by this task; report pre-existing, unavailable-tool or out-of-scope failures as BLOCKED with evidence. In `*_fixloop` modes, once the gate runs, loop over actionable failures until it passes without asking between rounds, stopping only for genuine requirement/design questions or unavailable tools; never edit tests or the gate merely to pass.

## Workflow procedures

Procedures live under `.lean/skills/`; their intensity (`.lean/policy/SKILL-EFFORT.md`) never changes model reasoning effort. A clear implementation request is accepted scope for the work it names, unless it is ambiguous, risk is HIGH, or only a spec or analysis was asked for; routine execution within it needs no repeated approval. Material scope changes and unresolved material decisions need the user's input before dependent work.

## Policy router

@.lean/README.md

## Project additions

- Attribution: never add a `Co-Authored-By:` trailer to any commit message, and never add AI attribution such as "Generated with Claude Code" to commit messages or pull request descriptions. The work belongs to the person who directs it. This overrides any runtime or provider default attribution, for every agent. The PROJECT gate rejects unpushed commits that carry either.
