---
name: lean-multi-agent
description: Controller and worker delegation with bounded ownership, portable model selection, evidence and optional parallel work.
---

# Lean Multi-Agent

Read `AGENTS.md`, `.lean/PROJECT.md`, and use `python3 .lean/scripts/workflow.py show` for repository mode and execution routing. This procedure applies when `execution` is `delegated`, the user explicitly requests workers, or independent review is required. In `direct`, normal implementation stays with the active agent. Repository mode does not select execution or review depth.

## Controller

1. Own the Task Contract, accepted scope, integration, validation, review coordination and final result. Create a workset before non-trivial work in `tracker` or `full`; `standard` and trivial work use session records. Reuse accepted decisions and never ask for approval already given.
2. Define bounded assignments with acceptance checks, dependencies, allowed files and exclusive ownership. Delegate one ready task by default in delegated execution, including small tasks. Concurrent workers need independent scopes and explicit user intent for parallel work. Keep one Controller slot and respect runtime limits.
3. Select the least costly capable model and supported effort by `.lean/policy/MODELS.md` using runtime options. Record requested and actually reported settings honestly. Require task-specific evidence that a cheaper option cannot meet the outcome and material constraints before selecting a premium model. A HIGH label or preference is not evidence; never authorize additional paid usage implicitly.
4. Record each dispatch before the call. In `full`, create an item for independently claimable non-trivial tasks and assign its exact ID; the worker must claim before editing. Use identical scope labels for shared files; scopes are exact strings, not directory containment.
5. Send contract, task ID, queue ID if needed, allowed files, checks, dependencies and handoff instructions. If delegation is required but unavailable, report BLOCKED; do not silently switch execution. Independent review remains required regardless of execution routing.
6. For blockers, preserve partial work and record the prerequisite. In `full`, add a queued dependency while the claim is held or arrange release then set the item BLOCKED; release alone makes the item READY. Do not redispatch blocked work before its prerequisite is resolved.
7. Verify worker evidence, synchronize records, run integrated checks and required review over the shipping delta. Worker or queue completion alone does not mark the workset DONE. The Controller owns the final Quality Gate and tracker transition.

## Dispatch record

Use the owning tracker Evidence section, or a user-visible session record for standard/trivial work:

```text
Dispatch TASK-01 [queue ID if applicable] | role=worker | requested model/effort=inherited/inherited | reason=task-specific capability choice | agent ID/ref=runtime identity or labeled task | reported model/effort=unavailable/unavailable
```

Record each new assignment or settings change. Requested settings are not proof of backend settings; use `unavailable` for metadata the runtime does not expose. Do not store credentials, raw prompts or model price assumptions.

## Worker

- Edit only assigned files and start only when dependencies and ownership are ready. In `full`, use `python3 .lean/scripts/workflow.py queue claim --id QNNNN --agent NAME --request-id UUID` with a generated stable random request ID before editing; retain it for a lost-response retry. Full-mode edits inside an existing claim require its ownership even when trivial.
- Keep leases alive with heartbeat before the 30-minute expiry. Add meaningful behavior tests and demonstrate bug regression fail-before/pass-after. Never weaken tests or scope to pass.
- On a blocker, stop edits and tell the Controller the cause, prerequisite, partial diff and task/queue ID. Coordinate record updates then release the claim. Do not poll waiting for dependencies.
- On completion, return changed files, concrete check evidence and integration risks; complete any claim with evidence. A worker cannot declare the whole task DONE.

## Checkout boundary

Shared checkouts require exclusive file ownership. Leases are local to a checkout; separate worktrees need a shared ownership/integration plan. Claim tokens are local coordination state, not a security boundary or external write authorization.

$ARGUMENTS
