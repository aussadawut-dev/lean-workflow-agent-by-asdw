---
name: lean-multi-agent
description: Controller/worker delegation with bounded ownership, model selection, evidence and optional parallel work.
user-invocable: true
argument-hint: "<bounded delegation task>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

# Lean Multi-Agent

Read `AGENTS.md`, `.lean/PROJECT.md`, and use `python3 .lean/scripts/workflow.py show` for repository mode and execution routing. This procedure applies when `execution` is `delegated`, the user explicitly requests workers, or independent review is required. In `direct`, normal implementation stays with the active agent. Repository mode does not select execution or review depth.

## Controller

1. Own the Task Contract, accepted scope, integration, validation, review coordination and final result. Create a workset before non-trivial work in `tracker` or `full`; `standard` and trivial work use session records. Reuse accepted decisions and never ask for approval already given.
2. Define bounded assignments with acceptance checks, dependencies, allowed files and exclusive ownership. Delegate one ready task by default in delegated execution, including small tasks. Concurrent workers need independent scopes and explicit user intent for parallel work. Keep one Controller slot and respect runtime limits. Size each assignment to a budget of a few files and about 50 tool calls: a worker resends its whole context on every call, so one long worker costs far more than two short ones. Split a larger slice by component or layer before dispatch; keep a slice that already fits whole, since a split adds a cold start. Where the runtime caps a role (Claude: `maxTurns` and `autoCompactWindow` in `.claude/agents/<role>.md`), back the budget with it and keep the brief's budget below that cap; Codex `spawn_agent` has no per-spawn turn cap, so there the brief carries the budget. A cap cuts a worker off wherever it is, so its edits may be half-applied (step 7).
3. Consult optional project catalog evidence alongside current runtime options; absent/stale entries do not justify an automatic refresh or a model substitution. Use `/lean-model-update` only for requested refreshes. Select the least costly capable model and supported effort by `.lean/policy/MODELS.md` using runtime options, and pass both in each spawn call that accepts them; inherit only with a recorded reason. Record requested and actually reported settings honestly. Require task-specific evidence that a cheaper option cannot meet the outcome and material constraints before selecting a premium model. A HIGH label or preference is not evidence; never authorize additional paid usage implicitly.
4. Record each dispatch before the call. In `full`, create an item for independently claimable non-trivial tasks and assign its exact ID; the worker must claim before editing. Use identical scope labels for shared files; scopes are exact strings, not directory containment. A claim the Controller holds keeps expiring while workers run: heartbeat it before each dispatch and when each worker returns (`python3 .lean/scripts/workflow.py queue heartbeat --id QNNNN --token TOKEN`), and give a worker that may outlast the remaining lease its own item and claim. A lapsed claim cannot be renewed; claim the item again with a new request ID.
5. Send contract, task ID, queue ID if needed, allowed files, checks, dependencies, budget and handoff instructions. Ask the worker to locate before reading (search for line numbers, then read only those ranges), edit rather than rewrite whole files, run only the tests for changed files while iterating, and run its full checks once before handoff. If delegation is required but unavailable, report BLOCKED; do not silently switch execution. Independent review remains required regardless of execution routing.
6. For blockers, preserve partial work and record the prerequisite. In `full`, add a queued dependency while the claim is held or arrange release then set the item BLOCKED; release alone makes the item READY. Do not redispatch blocked work before its prerequisite is resolved.
7. Before accepting a worker's result, inspect `git status` and the diff of its assigned files. Treat a missing handoff report as a cap or truncation: the edits are partial, so finish or redispatch the remainder as a new bounded slice, and release or claim again any item the worker held before redispatch. Verify worker evidence, synchronize records, run integrated checks and required review over the shipping delta. Worker or queue completion alone does not mark the workset DONE. The Controller owns the final Quality Gate and tracker transition.

## Dispatch record

Use the owning tracker Evidence section, or a user-visible session record for standard/trivial work:

```text
Dispatch TASK-01 [queue ID if applicable] | role=worker | requested model/effort=<sized model>/<sized effort> | reason=task size and capability choice | agent ID/ref=runtime identity or labeled task | reported model/effort=unavailable/unavailable
```

Record each new assignment or settings change. Requested settings are not proof of backend settings; use `unavailable` for metadata the runtime does not expose. Do not store credentials, raw prompts or model price assumptions.

## Worker

- Edit only assigned files and start only when dependencies and ownership are ready. In `full`, use `python3 .lean/scripts/workflow.py queue claim --id QNNNN --agent NAME --request-id UUID` with a generated stable random request ID before editing; retain it for a lost-response retry. Full-mode edits inside an existing claim require its ownership even when trivial.
- Keep leases alive with heartbeat before the 30-minute expiry. Add meaningful behavior tests and demonstrate bug regression fail-before/pass-after. Never weaken tests or scope to pass.
- Work within the assignment budget. When it runs out before the checks pass, stop at a consistent point and hand back changed files, check status and the remaining steps instead of continuing.
- On a blocker, stop edits and tell the Controller the cause, prerequisite, partial diff and task/queue ID. Coordinate record updates then release the claim. Do not poll waiting for dependencies.
- On completion, return changed files, concrete check evidence and integration risks; complete any claim with evidence. A worker cannot declare the whole task DONE.

## Checkout boundary

Shared checkouts require exclusive file ownership. Leases are local to a checkout; separate worktrees need a shared ownership/integration plan. Claim tokens are local coordination state, not a security boundary or external write authorization.

$ARGUMENTS
