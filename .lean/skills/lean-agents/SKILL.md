---
name: lean-agents
description: Spawn agents for independent tasks. Alone, spawns one agent per task that can run in parallel; with a model and xN, runs up to N agents at once on that model. Controller/worker rules, sizing, worktrees and dispatch records.
user-invocable: true
argument-hint: "[<model> xN] [task]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md`; keep model reasoning effort separate.

# Lean Agents

Read `AGENTS.md`, `.lean/PROJECT.md`, `.lean/policy/MODELS.md` and `python3 .lean/bin/lean mode show`. Without this skill, spawning follows the default level in MODELS.md (one sized agent at a time, only when cheaper). Invoking this skill is the user's explicit request for parallel agents:

| Invocation | Level | Agents |
|---|---|---|
| `/lean-agents [task]` | `max` | one per task that can run in parallel, each sized S/M/L/XL |
| `/lean-agents <model> xN [task]` (or "use 3 sonnet") | `explicit` | up to N at once, all on that model; further tasks run as slots free up |

`<model>` is a model ID or alias the provider accepts (`sonnet`, `claude-opus-5-5`, `gpt-6.1-sol`, `gemini-4-argon-high`); `xN` is the agent count.

## Controller

1. Own the Task Contract, accepted scope, integration, validation, review coordination and final result. Create a workset before non-trivial work in `tracker` or `full`; reuse accepted decisions and never ask for approval already given.
2. Split the work into tasks with acceptance checks, dependencies, owned files and a size, and write them as a task list: `{"tasks": [{"id": "api", "files": ["src/api.py"], "size": "M", "deps": [], "prompt": "..."}]}`. Two tasks never own the same file. Keep a task to a few files and about 50 turns (model requests; parallel tool calls in one turn count once): a worker resends its whole context on every call, so one long worker costs far more than two short ones. Split a larger task by component or layer; keep one that fits whole.
3. Plan: `python3 .lean/bin/lean spawn plan --tasks <file> --level max` (or `-n N --model <model>` for the explicit level). Show the user the plan's agent count, waves and notes before dispatch. Fewer parallel tasks than requested is reported, not padded.
4. Dispatch each wave, one of two ways:
   - **In session**: the runtime's subagent tool, passing each task's `model` and `effort` from the plan (Claude Agent tool `model` + `effort`; Codex `spawn_agent` with model, reasoning effort and `fork_turns: "none"` plus a self-contained brief). Concurrent in-session workers share this checkout, so file ownership must be exclusive.
   - **As processes**: `python3 .lean/bin/lean spawn run --plan <plan.json>` starts headless provider CLIs in separate git worktrees with per-agent progress bars and API-key environment variables removed (a login the CLI stored itself, such as a Codex API-key `auth.json`, still bills; confirm subscription logins). Commit first or pass `--allow-dirty`; worktrees start from HEAD. It refuses while an application target is selected (its worktrees would not contain the application); use in-session subagents there.
5. Brief every worker with the contract, task ID, queue ID if any, owned files, checks, dependencies, budget and handoff instructions. Ask it to locate before reading, edit rather than rewrite whole files, report progress with `lean progress set`, run only the tests for changed files while iterating and its full checks once before handoff. The budget never removes required behavior tests: name each task's required tests in the brief, and split the task rather than drop them.
6. Record each dispatch before the call (format below). In `full`, give each independently claimable task a queue item and have the worker claim it before editing; heartbeat a claim you hold before each dispatch and when each worker returns.
7. Before accepting a result, inspect `git status` and the diff of the task's files (for `spawn run`, `git -C <worktree> diff HEAD`, then apply it to this checkout). Treat a missing handoff report as a cap or truncation: the edits are partial, so finish or redispatch the remainder as a new task. Do not resume a worker that spent its budget; send the remainder fresh. Resume only to finish a handoff report or recover from a transient runtime error. Verify evidence, integrate, run integrated checks and required review over the shipping delta, then `lean spawn clean <run>`. Worker or queue completion alone does not mark the workset DONE.
8. For blockers, preserve partial work and record the prerequisite. Do not redispatch blocked work before its prerequisite is resolved. If delegation is required but unavailable, report BLOCKED; do not silently switch execution. Independent review remains required regardless of routing.

## Dispatch record

Use the owning tracker Evidence section, or a user-visible session record for standard/trivial work:

```text
Dispatch TASK-01 [queue ID] | level=default|max|explicit | size=M | requested model/effort=<model>/<effort> | context=fresh or full-history (reason) | agent=<runtime identity or worktree> | reported model/effort=<from runtime metadata, or unavailable>
```

Never use bare `inherited/inherited`. Requested settings are not proof of backend settings: report a model only from runtime metadata (a subagent transcript's `model` field, the command `spawn run` executed), not from a pane banner that shows session defaults. Do not store credentials, raw prompts or price assumptions.

## Worker

- Edit only the owned files and start only when dependencies and ownership are ready. In `full`, claim the exact queue item (`lean queue claim --id QNNNN --agent NAME --request-id UUID`) before editing and heartbeat before the 30-minute expiry.
- Add meaningful behavior tests and demonstrate bug regression fail-before/pass-after. Never weaken tests or scope to pass.
- Work within the budget. When it runs out before the checks pass, stop at a consistent point and hand back changed files, check status and remaining steps.
- On a blocker, stop edits and report the cause, prerequisite, partial diff and task/queue ID.
- On completion, return changed files, concrete check evidence and integration risks. A worker cannot declare the whole task DONE.

$ARGUMENTS
