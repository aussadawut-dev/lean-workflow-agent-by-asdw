# Spawn and delegation

[Back to README](../README.md)

Run the CLI examples from the repository root.

## Who does what

In `delegated` execution, the active agent becomes Controller and gives a worker a bounded assignment. The Controller owns scope, coordination, integration, validation, review and the final report.

In `direct` execution, the active agent implements the work itself and follows the same checks. Mode and execution are separate choices. See [model and effort selection](models.md) for choosing capable settings and checking what the runtime actually started.

| Role | Responsibility |
|---|---|
| Controller | Plan accepted work, assign clear boundaries, integrate and verify the result. |
| Worker | Edit assigned files, run relevant tests and return the diff, evidence and risks. |
| Independent reviewer | Review the contract and final diff in a fresh context, without the author's reasoning. |

Parallel workers need explicit user intent, independent tasks and exclusive file ownership. The diagram below shows one worker. HIGH-depth review needs an independent reviewer whether implementation is direct or delegated.

## The shared sequence

```mermaid
sequenceDiagram
    actor User
    participant Controller as Active agent / Controller
    participant Runtime as Subagent runtime
    participant Worker as Bounded worker
    participant Records as Tracker / local queue
    participant Reviewer as Independent reviewer
    participant Checks as Project checks / Quality Gate

    User->>Controller: Request work and acceptance outcome
    Controller->>Controller: Read rules, state contract and settle scope/routing
    opt Non-trivial work in tracker/full
        Controller->>Records: Create workset; full also needs queue items
    end
    Controller->>Runtime: Dispatch bounded assignment with capable settings
    Runtime->>Worker: Files, checks, handoff and resolved settings
    Runtime-->>Controller: Identity and reported model/effort, or unavailable
    opt Full mode
        Worker->>Records: Claim exact item with stable random request ID
        Records-->>Worker: Token, scope and lease expiry
    end
    Worker->>Worker: Implement and test; bugs fail before and pass after the fix
    opt Long work in full mode
        Worker->>Records: Renew the owned lease before expiry
    end
    alt Worker is blocked
        Worker-->>Controller: Cause, prerequisite, partial diff and task ID
        Controller->>Records: Record blocker/dependency when applicable
        Worker->>Records: Release owned claim when applicable
        Controller-->>User: BLOCKED with preserved progress
    else Worker returns implementation
        Worker-->>Controller: Diff, test evidence and integration risks
        Controller->>Checks: Verify evidence and run integrated validation
        Checks-->>Controller: Results
        opt Validation passes and HIGH review is required
            Controller->>Runtime: Dispatch fresh reviewer with contract and shipping diff
            Runtime->>Reviewer: Independent context without author reasoning
            Runtime-->>Controller: Identity and reported settings, or unavailable
            Reviewer-->>Controller: PASS / REWORK, findings and coverage
        end
        Note over Controller,Checks: Other depths still need review; REWORK returns to bounded repair and validation
        opt Validation and required review pass in full mode
            Controller->>Worker: Finalize owned item with verified evidence
            Worker->>Records: Complete using token and remove active lease
        end
        Controller->>Records: Synchronize evidence and status where enabled
        Controller->>Checks: Run lean-gate and verify completion conditions
        Checks-->>Controller: Gate and acceptance results
        Controller->>Records: DONE only when every condition holds
        Controller-->>User: DONE, BLOCKED or FAILED with evidence
    end
```

If required delegation or independent review is unavailable, report BLOCKED. A worker's completion does not complete the workset on its own. Record requested and runtime-reported settings separately. Model options are alternatives for a worker/reviewer; they are not a request to start every model.

Review is required at the contract's depth. REWORK goes back through repair and validation within the review limit. After a second REWORK, there is one final repair/review pass. PASS ends the cycle.

## Codex

Codex discovers shared procedures through `.agents/skills/` links. It runs validation explicitly or through its trusted, activated lifecycle adapter. Claude's hook settings do not configure Codex.

The Controller verifies the integrated work, required review and completion evidence. HIGH review uses a fresh reviewer. Available model/effort controls depend on the runtime; check [official subagent settings](https://learn.chatgpt.com/docs/agent-configuration/subagents) and record what was actually exposed.

## Claude

Claude starts through the `CLAUDE.md` import of AGENTS. SessionStart reads onboarding state and seeds a change baseline, keeping earlier gate refusals. It does not validate the project.

The shared reviewer definition keeps `model: inherit` only as a portable fallback. Each invocation passes the model and effort sized by the [model policy](../.lean/policy/MODELS.md) when the Agent tool accepts them. See [Claude subagent documentation](https://code.claude.com/docs/en/sub-agents#choose-a-model) for runtime controls.

After the Controller checks acceptance, validation, review and records, the Stop hook follows the shared auto/manual policy. In auto mode it runs configured checks; an eligible unchanged cached state can reuse a passing run. An outstanding refusal prevents cache skipping.

Failed checks return evidence to the agent. Repair task-caused failures, revalidate and review the changed diff. If unresolved, report BLOCKED/FAILED. Continued Stop handling can release a turn as UNVERIFIED; that release cannot turn a failure into a pass.

Hooks check deterministic commands. The Controller still needs to verify acceptance, review independence and tracker/queue synchronization. See [quality and runtime](quality-and-runtime.md) for caching, locking, manual mode and activation limits.
