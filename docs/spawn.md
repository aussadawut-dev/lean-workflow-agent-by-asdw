# Spawn and delegation

[Back to README](../README.md)

Run CLI examples from the repository root.

## Overview

The Controller chooses a model, assigns a bounded worker, validates the result, and completes the required review and Quality Gate. The examples show delegated work; direct execution follows the same checks with the Controller doing the implementation.

Model options below match the [documented model list](models.md#documented-model-options), checked on 2026-10-06. Select an available capable option; premium choices still require evidence and any required billing authorization.

### Codex

```mermaid
sequenceDiagram
    actor User
    participant Controller as Codex Controller<br/>session model
    participant Light as Worker / reviewer<br/>gpt-6-luna<br/>gpt-5.6-luna
    participant General as Worker / reviewer<br/>gpt-6.1-sol<br/>gpt-6-sol<br/>gpt-5.6-sol<br/>gpt-5.6-terra<br/>gpt-5.5
    participant Advanced as Worker / reviewer<br/>gpt-6-astra
    participant Inherited as Worker / reviewer<br/>inherit / default<br/>other supported<br/>model ID
    participant Checks as Validation and<br/>Quality Gate

    User->>Controller: Request task
    Controller->>Controller: Set contract and choose an available capable model
    alt Focused task and sufficient capability
        Controller->>Light: Spawn bounded assignment with supported effort
        Light-->>Controller: Evidence or review verdict
    else Implementation or focused review
        Controller->>General: Spawn bounded assignment with supported effort
        General-->>Controller: Evidence or review verdict
    else Stronger capability justified by evidence
        Controller->>Advanced: Spawn bounded assignment with supported effort
        Advanced-->>Controller: Evidence or review verdict
    else Use session/default settings or an allowed ID
        Controller->>Inherited: Spawn bounded assignment with supported effort
        Inherited-->>Controller: Evidence or review verdict
    end
    Controller->>Checks: Validate changes
    Checks-->>Controller: Validation result
    opt Validation passes and HIGH review is required
        Controller->>Controller: Repeat selection for a fresh independent reviewer
        Note over Controller,Checks: Reviewer receives contract and diff, without author reasoning
    end
    Controller->>Checks: Verify required review, acceptance and gate
    Checks-->>Controller: Completion result
    Controller-->>User: DONE if all conditions pass, otherwise report blocker/failure
```

### Claude

```mermaid
sequenceDiagram
    actor User
    participant Controller as Claude Controller<br/>session model
    participant Haiku as Worker / reviewer<br/>haiku
    participant Sonnet as Worker / reviewer<br/>sonnet
    participant Opus as Worker / reviewer<br/>opus
    participant Fable as Worker / reviewer<br/>fable
    participant Inherited as Worker / reviewer<br/>inherit /<br/>full model ID
    participant Checks as Validation and<br/>Quality Gate

    User->>Controller: Request task
    Controller->>Controller: Set contract and choose an available capable model
    alt Select a capable available option
        Controller->>Haiku: Spawn bounded assignment with supported effort
        Haiku-->>Controller: Evidence or review verdict
    else Select another capable available option
        Controller->>Sonnet: Spawn bounded assignment with supported effort
        Sonnet-->>Controller: Evidence or review verdict
    else Select with justification and any required authorization
        Controller->>Opus: Spawn bounded assignment with supported effort
        Opus-->>Controller: Evidence or review verdict
    else Select if available and suitable
        Controller->>Fable: Spawn bounded assignment with supported effort
        Fable-->>Controller: Evidence or review verdict
    else Use session/default settings or an allowed ID
        Controller->>Inherited: Spawn bounded assignment with supported effort
        Inherited-->>Controller: Evidence or review verdict
    end
    Controller->>Checks: Validate changes
    Checks-->>Controller: Validation result
    opt Validation passes and HIGH review is required
        Controller->>Controller: Repeat selection for a fresh independent reviewer
        Note over Controller,Checks: Reviewer receives contract and diff, without author reasoning
    end
    Controller->>Checks: Verify required review, acceptance and gate
    Checks-->>Controller: Completion result
    Controller-->>User: DONE if all conditions pass, otherwise report blocker/failure
```

Review is required at every depth; HIGH uses an independent reviewer. REWORK returns to repair and validation within the review limit. Each model lane is an alternative for one worker or fresh reviewer, not a request to spawn every model. Runtime-reported settings must be checked. Queue, lease, hook and failure-handling steps appear below.

## Detailed sequences

Execution is independent of mode: `direct` uses the active agent; `delegated` makes it the Controller with a bounded worker. Parallel workers require explicit user intent, independent tasks and exclusive file ownership. HIGH-depth review requires a fresh independent reviewer with either execution setting. See [model and effort selection](models.md) for dispatch settings.

Detailed diagrams focus on roles, ownership, validation and runtime control. Named model options appear in the overview lanes; select from available models under the [model policy](../.lean/policy/MODELS.md). Record requested and reported settings separately.

See the official [Codex subagent settings](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [Claude subagent model selection](https://code.claude.com/docs/en/sub-agents#choose-a-model).

<details>
<summary>Codex: detailed sequence</summary>

## Codex: Controller, worker and independent reviewer

```mermaid
sequenceDiagram
    actor User
    participant Controller as Codex Controller
    participant Runtime as Codex subagent runtime
    participant Worker as Worker subagent
    participant Queue as Local queue / tracker
    participant Reviewer as Independent reviewer
    participant Checks as Project checks and<br/>Quality Gate

    User->>Controller: Request task
    Controller->>Controller: Read shared rules, set contract, scope and routing
    opt Tracker/full and non-trivial work
        Controller->>Queue: Create workset and full-mode task items
    end
    Controller->>Controller: Select capable worker settings and record reason
    Controller->>Runtime: Spawn worker with selected settings and bounded assignment
    Note over Controller,Runtime: Delegation unavailable when required means BLOCKED
    Runtime->>Worker: Deliver files, checks, handoff instructions and resolved settings
    Runtime-->>Controller: Worker identity and reported model/effort, or unavailable
    opt Full mode ownership
        Worker->>Queue: Claim exact item with stable random request ID
        Queue-->>Worker: Token, scope ownership and lease expiry
    end
    Worker->>Worker: Edit assigned files, bug tests fail before / pass after fix
    opt Long-running full-mode work
        Worker->>Queue: Heartbeat owned lease before expiry
    end
    alt Worker blocked
        Worker-->>Controller: Cause, prerequisite, partial diff and task ID
        Controller->>Queue: Record blocker/dependency when applicable
        Worker->>Queue: Release owned claim when applicable
        Controller-->>User: BLOCKED with preserved progress
    else Worker returns completed implementation
        Worker-->>Controller: Changed files, concrete test evidence and risks
        Controller->>Checks: Verify evidence and run integrated deterministic checks
        Checks-->>Controller: Results
        opt Checks pass and HIGH review depth is required
            Controller->>Controller: Select capable reviewer settings and record reason
            Controller->>Runtime: Spawn fresh reviewer with selected settings, contract and shipping diff
            Note over Runtime,Reviewer: Do not include the author's reasoning
            Runtime->>Reviewer: Independent assignment with resolved model/effort
            Runtime-->>Controller: Reviewer identity and reported model/effort, or unavailable
            Reviewer-->>Controller: PASS / REWORK, findings and scope
        end
        Note over Controller,Checks: Other depths use the required review, REWORK returns to bounded repair and validation
        opt Validation and required review pass in full mode
            Controller->>Worker: Finalize owned queue item with verified evidence
            Worker->>Queue: Complete using token, remove active lease
            Queue-->>Controller: Queue completion status
        end
        Controller->>Queue: Synchronize evidence and current status in enabled records
        Controller->>Checks: Explicitly run /lean-gate completion procedure
        Checks-->>Controller: Gate commands and completion evidence results
        Controller->>Queue: Synchronize enabled records, DONE only if all conditions hold
        Controller-->>User: DONE, BLOCKED or FAILED with evidence
    end
```

Codex uses the adapters in `.agents/skills/` to follow shared procedures. Claude's hook settings do not run Codex checks. Worker completion alone never completes the workset. Concurrent workers require explicit parallel intent, independent tasks and exclusive file ownership; the diagram shows the default single worker.

</details>

<details>
<summary>Claude: detailed sequence</summary>

## Claude: Controller, worker, reviewer and hooks

```mermaid
sequenceDiagram
    actor User
    participant Runtime as Claude runtime
    participant Hooks as SessionStart / Stop hooks
    participant Controller as Claude Controller
    participant Worker as Worker subagent
    participant Queue as Local queue / tracker
    participant Reviewer as reviewer subagent
    participant Checks as Project checks and<br/>Quality Gate

    Runtime->>Hooks: SessionStart event
    Hooks->>Hooks: Read onboarding state and seed gate baseline
    Hooks-->>Runtime: Setup guidance when needed, preserve prior gate refusal
    User->>Controller: Request task
    Controller->>Controller: Read CLAUDE import of AGENTS, project facts and routing
    Controller-->>User: Task Contract before changes
    opt Tracker/full and non-trivial work
        Controller->>Queue: Create workset and full-mode task items
    end
    Controller->>Controller: Select capable worker settings and record reason
    Controller->>Runtime: Dispatch bounded worker with selected settings
    Note over Controller,Runtime: Delegation unavailable when required means BLOCKED
    Runtime->>Worker: Files, acceptance checks, handoff and resolved model/effort
    Runtime-->>Controller: Worker identity and reported model/effort, or unavailable
    opt Full mode ownership
        Worker->>Queue: Claim exact item with stable request ID
        Queue-->>Worker: Token and lease expiry
    end
    Worker->>Worker: Implement and test, show fail-before/pass-after for bugs
    opt Long-running full-mode work
        Worker->>Queue: Heartbeat owned lease before expiry
    end
    alt Worker blocked
        Worker-->>Controller: Cause, prerequisite, partial diff and task ID
        Controller->>Queue: Record blocker/dependency when applicable
        Worker->>Queue: Release owned claim when applicable
        Controller-->>User: BLOCKED with preserved progress
    else Worker returns completed implementation
        Worker-->>Controller: Diff, check evidence and integration risks
        Controller->>Checks: Run integrated deterministic validation
        Checks-->>Controller: Results
        opt Validation passes and HIGH review depth is required
            Controller->>Controller: Record inherited reviewer settings
            Controller->>Runtime: Dispatch reviewer with contract and shipping diff
            Runtime->>Reviewer: Fresh context with inherited session settings
            Runtime-->>Controller: Reviewer identity and reported model/effort, or unavailable
            Note over Runtime,Reviewer: Contract and diff only, without author's reasoning
            Note over Runtime,Reviewer: Repository reviewer defaults to inherited model and effort
            Reviewer-->>Controller: PASS / REWORK, findings and scope
        end
        Note over Controller,Checks: Other depths still require review, REWORK follows bounded repair and revalidation
        opt Validation and required review pass in full mode
            Controller->>Worker: Finalize owned queue item with verified evidence
            Worker->>Queue: Complete using token, remove active lease
        end
        Controller->>Queue: Synchronize enabled records with evidence and current status
        Controller->>Checks: Run /lean-gate commands and verify all completion conditions
        Checks-->>Controller: Gate results and evidence assessment
        Controller->>Queue: Synchronize final status, DONE only if every condition holds
        Controller->>Runtime: Attempt to finish turn
        Runtime->>Hooks: Stop event
        Hooks->>Checks: Run configured gate commands if repository state needs checks
        Note over Hooks,Checks: Unchanged cached state can skip checks, an outstanding refusal prevents cache skip
        Checks-->>Hooks: Pass, fail or missing tool
        alt Hook checks pass or valid unchanged-state skip
            Hooks-->>Runtime: Allow turn to finish
            Controller-->>User: Result with evidence, report BLOCKED / FAILED if conditions are missing
        else Gate command fails or cannot run
            Hooks-->>Runtime: Exit 2, block finishing and return evidence
            Runtime-->>Controller: Continue with gate result
            Controller->>Controller: Repair task-caused failures and revalidate/review changed diff
            Controller-->>User: BLOCKED / FAILED if unresolved
        end
    end
```

Claude's Stop hook enforces deterministic gate commands; it does not prove acceptance evidence, review independence or tracker/queue synchronization. The Controller must verify those conditions. The hook avoids recursively blocking a continuation already marked `stop_hook_active`; that guard does not authorize declaring DONE after a failed gate.

</details>
