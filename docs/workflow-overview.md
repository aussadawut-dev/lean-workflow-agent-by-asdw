# Workflow overview

[Back to README](../README.md)

Run CLI examples from the repository root.

These diagrams describe the workflow, not an automatic scheduler. The active agent owns the task; it becomes the Controller when delegating. Modes add records independently of execution and review depth. A worker is used when execution is `delegated` or workers are explicitly requested. HIGH-depth review needs a fresh independent reviewer even in `direct` execution.

## Level 0: complete workflow

```mermaid
sequenceDiagram
    actor User
    participant Agent as Active agent / Controller
    participant Rules as Project contract and configuration
    participant Work as Implementation and tests
    participant Review as Review at required depth
    participant Gate as Quality Gate and records

    User->>Agent: Request work and acceptance outcome
    Agent->>Rules: Read AGENTS, policy router, project facts and mode/execution
    Rules-->>Agent: Scope rules, commands and configured routing
    Agent-->>User: State Task Contract before changes
    opt Material scope or decision remains unresolved
        Agent->>User: Resolve decision before dependent work
        User-->>Agent: Accepted scope / decision
    end
    opt Non-trivial task in tracker or full mode
        Agent->>Gate: Create workset, full also creates queue items
    end
    Agent->>Work: Implement directly or dispatch a bounded worker
    Note over Agent,Work: Full-mode scope edits require ownership before editing
    opt Bug fix
        Work->>Work: Demonstrate regression test fails before fix
    end
    Work->>Work: Make changes and run meaningful applicable tests
    Work-->>Agent: Diff, evidence and integration risks
    Agent->>Gate: Run deterministic project validation
    Gate-->>Agent: Check results
    alt Validation passes
        Agent->>Review: Review Task Contract and shipping diff
        Note over Agent,Review: Depth is the deeper of risk and quality floor, HIGH is independent
        Review-->>Agent: PASS or REWORK with concrete findings
        opt REWORK within bounded review cycle
            Agent->>Work: Repair findings, revalidate and resubmit for review
        end
        Agent->>Gate: Verify acceptance, tests, final review coverage and records
        Note over Agent,Gate: Full: complete owned queue items with evidence, then synchronize tracker
        Gate-->>Agent: Completion conditions satisfied or missing
        alt Final review PASS and all completion conditions satisfied
            Agent-->>User: DONE with evidence and any stated limits
        else Required evidence, tooling or review missing
            Agent-->>User: BLOCKED or FAILED with cause and next step
        end
    else Validation fails or cannot run
        Agent->>Agent: Repair task-caused failures and rerun, preserve unrelated failures
        Agent-->>User: BLOCKED / FAILED if unresolved, with evidence
    end
    opt User explicitly requests queue cleanup
        Agent->>Gate: Preview, then lock and archive selected DONE items
        Gate-->>Agent: Preserved history and cleanup result
        Agent-->>User: Report archived items and any partial progress
    end
```

A PASS ends its review cycle. After the second REWORK, only one final repair/review pass is allowed; another REWORK reports BLOCKED. Changes after PASS open a new contract. Commit, push and merge are separate actions performed when requested.
