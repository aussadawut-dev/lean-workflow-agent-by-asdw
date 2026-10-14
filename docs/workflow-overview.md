# Workflow overview

[Back to README](../README.md)

This is the path a task follows. The active agent owns it and becomes Controller when delegating. Modes add records; execution decides who implements; review depth decides how the result is checked.

The diagram describes the procedure. Workers are used when execution is `delegated` or explicitly requested. HIGH-depth review needs a fresh independent reviewer even in `direct` execution.

## From request to completion

```mermaid
sequenceDiagram
    actor User
    participant Agent as Active agent / Controller
    participant Rules as Project rules and settings
    participant Work as Implementation and tests
    participant Review as Review at required depth
    participant Gate as Quality Gate and records

    User->>Agent: Describe the work and acceptance outcome
    Agent->>Rules: Read AGENTS, router, project facts and mode/execution
    Rules-->>Agent: Scope rules, commands and routing
    Agent-->>User: State Task Contract before changes
    opt Important scope or decision is still open
        Agent->>User: Settle it before dependent work
        User-->>Agent: Accepted scope / decision
    end
    opt Non-trivial task in tracker/full
        Agent->>Gate: Create workset; full also creates queue items
    end
    Agent->>Work: Implement directly or dispatch a bounded worker
    Note over Agent,Work: Full-mode scope edits need ownership first
    opt Bug fix
        Work->>Work: Show the regression test failing before the fix
    end
    Work->>Work: Make changes and run meaningful applicable tests
    Work-->>Agent: Diff, evidence and integration risks
    Agent->>Gate: Run deterministic project validation
    Gate-->>Agent: Check results
    alt Validation passes
        Agent->>Review: Review contract and final diff
        Note over Agent,Review: Use the deeper of risk and quality floor; HIGH is independent
        Review-->>Agent: PASS or REWORK with concrete findings
        opt REWORK within the review limit
            Agent->>Work: Repair, revalidate and review again
        end
        Agent->>Gate: Verify acceptance, tests, review coverage and records
        Note over Agent,Gate: Full mode completes owned queue items with evidence, then synchronizes tracker
        Gate-->>Agent: Completion conditions met or missing
        alt Review passes and all conditions are met
            Agent-->>User: DONE with evidence and stated limits
        else Required evidence, tools or review are missing
            Agent-->>User: BLOCKED / FAILED with cause and next step
        end
    else Validation fails or cannot run
        Agent->>Agent: Repair task-caused failures and preserve unrelated ones
        Agent-->>User: BLOCKED / FAILED if unresolved, with evidence
    end
    opt User requests queue cleanup
        Agent->>Gate: Preview, then lock and archive selected DONE items
        Gate-->>Agent: Preserved history and cleanup result
        Agent-->>User: Report archived items and partial progress
    end
```

PASS ends a review cycle. After a second REWORK, only one final repair/review pass remains; another REWORK reports BLOCKED. Changes after PASS need a new contract.

Commit, push, merge and release are separate actions when requested. For more detail, see [skills](skills.md), [quality and runtime](quality-and-runtime.md), and [delegation](spawn.md).
