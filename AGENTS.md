# Agent Instructions

Lean Workflow Baseline 5.0.0. This file is the canonical contract for all coding agents (Claude, Codex, agy).

**Before any task, read this file and `.lean/README.md`.** In Claude, both are already loaded through the `CLAUDE.md` imports; do not read them again.
Explicit user instructions take precedence. The active agent owns the task unless the project records a different Controller or primary agent. No provider owns the workflow by default. Keep shared rules here; `CLAUDE.md` imports them. Every workflow command is `python3 .lean/bin/lean <command>` (`lean --help` lists them).

## Core rules

- Before changing files, write one contract line as the first line of your reply, before any preamble, plan or tool call (or start a field block there):
  `Contract: risk=<LOW|MEDIUM|HIGH> quality=<STANDARD|HIGH|VERY_HIGH> acceptance=<observable check>`
  For a trivial task: `Contract: trivial (<reason>)`. Infer values; do not ask the user. Risk rules and the block form: `.lean/policy/CONTRACTS.md`.
  Hooks deny only write tools and writing shell commands until the contract is bound; reads and inspection run first. Claude's guard reads the contract from that first line once the reply is saved, which can wait for the first tool result, so in Claude run `declare` only when the turn's first tool call writes, to replace a bound contract, or after a write was denied. Where the guard cannot read a transcript (Codex, agy), first run `python3 .lean/bin/lean contract declare --contract '<one line>'` as a command of its own. Each new user prompt clears it; in Claude, a prompt typed while the agent is still working keeps it, so declare again only if that prompt changes the task.
- Show progress: on entering each phase run `python3 .lean/bin/lean progress set <phase> [--done N --total M] [--task '<title>']` and put the bar it prints in your reply (`.lean/policy/WORKFLOW.md`).
- Use the smallest sufficient context: impact-based context selection in `.lean/policy/CONTEXT.md`. Do not read workflow internals (`.lean/lean/`, `.lean/policy/`) unless the task needs them.
- Behavior changes require meaningful tests. Run only the tests a change can affect while working (`lean test --changed`); `.lean/policy/TESTING.md`.
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

- Read `.lean/PROJECT.md` before unfamiliar work. `python3 .lean/bin/lean mode show` reads mode and execution. Missing configuration uses unconfigured `standard`/`direct`; do not silently select a heavier mode.
- For an application target (a submodule under `targets/`), start from Lean and run `python3 .lean/bin/lean target context`. Read its `project_file` and target instructions. Workflow rules and tools stay in `workflow_root`; PROJECT, config, trackers, queue and runtime state stay in `record_root`; application code, commands and Git operations use `project_root`. `lean mode|tracker|queue|effort|models` select the target's records by default; `--root` overrides. Run the target gate explicitly where hooks do not (Codex without trust, agy) and keep Lean's own gate for workflow changes. Never install workflow files into the target or silently fall back when its context is invalid.
- Spawning follows `.lean/policy/MODELS.md` and the project model list (`lean models`, `.lean/models.json`): at most `max_agents` (default 1) agent at a time, sized S/M/L/XL to its task, and only when spawning costs less than finishing in this session. `/lean-agents` alone spawns one agent per task that can run in parallel; `/lean-agents <model> xN` runs up to N agents at once on that model (further tasks wait for a free slot). Pass the sized model and effort on every spawn whose tool accepts them, and record requested and reported settings; never use bare `inherited/inherited`. Spawned CLIs use the subscription login: `lean spawn run` removes metered API keys from their environment.
- `delegated` makes the active agent the Controller: it delegates bounded work, including small work, to one capable worker and keeps planning, scope, validation, integration, review and reporting (`.lean/skills/lean-agents/SKILL.md`). If required delegation is unavailable, report BLOCKED. Concurrent workers always need independent tasks and exclusive file ownership.
- For HIGH review depth, use an independent reviewer: Claude's `reviewer` subagent (`.claude/agents/reviewer.md`), or a fresh Codex or agy subagent or session (never a fork; `.lean/policy/REVIEW.md`). Give it `.lean/roles/reviewer.md`, the Task Contract and shipping diff without the author's reasoning. Select model and effort by `.lean/policy/MODELS.md`; report BLOCKED when required independence is unavailable.
- Claude hooks live in `.claude/settings.json`; Codex hooks in `.codex/hooks.json` apply only after runtime trust; agy has no hooks, so run the gate explicitly (`lean gate run`). Neither provider's settings or permissions apply to another. Optional `.lean/gate.json` sets gate automation (`auto|manual|auto_fixloop|manual_fixloop`, `lean gate mode`) for every provider (`.lean/policy/QUALITY.md`); `manual` and `manual_fixloop` Stops report NOT_RUN and require user authorization before starting a full gate run, and deferral never permits DONE or waives acceptance or review.
- If the Quality Gate fails in `auto` or `manual` mode, fix only failures caused by this task and report pre-existing, unavailable-tool or out-of-scope failures as BLOCKED with evidence. In `auto_fixloop` or `manual_fixloop` mode, once the gate runs, auto-loop over actionable code, test and lint failures until the gate passes without asking between rounds, stopping only for genuine requirement/design questions or unavailable tools; never edit tests or the gate merely to pass.

## Workflow procedures

Procedures live under `.lean/skills/`; their intensity follows `.lean/policy/SKILL-EFFORT.md` and never changes model reasoning effort.
Use accepted scope and decisions: a clear implementation request is accepted scope for the work it names, unless the request is ambiguous, risk is HIGH, or only a spec or analysis was asked for; routine execution within accepted scope needs no repeated approval. Material scope changes and unresolved material decisions need the user's input before dependent work.

## Policy router

@.lean/README.md

## Project additions

- Attribution: never add a `Co-Authored-By:` trailer to any commit message, and never add AI attribution such as "Generated with Claude Code" to commit messages or pull request descriptions. The work belongs to the person who directs it. This overrides any runtime or provider default attribution, for every agent. The PROJECT gate rejects unpushed commits that carry either.
