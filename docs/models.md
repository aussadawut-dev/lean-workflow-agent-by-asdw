# Model and effort selection

[Back to README](../README.md)

Run CLI examples from the repository root.

## Overview

Choose a model that can handle the assignment, use supported effort, and check what the runtime actually started. The main agent keeps its session settings. All documented named options are listed below; selection examples are not fixed defaults.

### Documented model options

Snapshot checked on **2026-10-06**. These are all named options in the cited Codex model page and Claude subagent model section, rather than a fixed runtime allowlist. Availability depends on the account, client and runtime. Custom providers can expose additional IDs.

| Provider | Named options | Other selection forms |
|---|---|---|
| Codex | `gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-luna`, `gpt-6-astra` | Inherited/default settings or another runtime-supported ID |
| Codex, earlier options | `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5` | `gpt-5.5` retires from Codex with ChatGPT sign-in on 2026-10-14 |
| Claude aliases | `haiku`, `sonnet`, `opus`, `fable` | `inherit` or an allowed full model ID, e.g. `claude-opus-5-5`, `claude-sonnet-5` |

Sources: [Codex models](https://learn.chatgpt.com/docs/models), [Codex subagent settings](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Claude model selection](https://code.claude.com/docs/en/sub-agents#choose-a-model). Retired Codex sign-in models are excluded from current choices; API-key/provider availability must be checked separately.

### Codex

```mermaid
sequenceDiagram
    participant Controller as Codex Controller<br/>session model
    participant Light as Worker / reviewer<br/>gpt-6-luna<br/>gpt-5.6-luna
    participant General as Worker / reviewer<br/>gpt-6.1-sol<br/>gpt-6-sol<br/>gpt-5.6-sol<br/>gpt-5.6-terra<br/>gpt-5.5
    participant Advanced as Worker / reviewer<br/>gpt-6-astra
    participant Inherited as Worker / reviewer<br/>inherit / default<br/>other supported<br/>model ID

    Controller->>Controller: Check availability, supported effort and task needs
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
    Controller->>Controller: Record runtime-reported model/effort or unavailable
```

### Claude

```mermaid
sequenceDiagram
    participant Controller as Claude Controller<br/>session model
    participant Haiku as Worker / reviewer<br/>haiku
    participant Sonnet as Worker / reviewer<br/>sonnet
    participant Opus as Worker / reviewer<br/>opus
    participant Fable as Worker / reviewer<br/>fable
    participant Inherited as Worker / reviewer<br/>inherit /<br/>full model ID

    Controller->>Controller: Check availability, supported effort and task needs
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
    Controller->>Controller: Record runtime-reported model/effort or unavailable
```

Each model lane is an alternative, not a concurrent agent. A fresh reviewer can use the same model as the worker. Hard reasoning, premium selection, unavailable settings and retry rules are covered in the detailed sequences below; the quality floor and any required billing authorization still apply.

## Detailed sequences

## Reading the model examples

The sequences show illustrative settings, not fixed assignments or confirmed backend values. Examples were checked on 2026-10-06. Recheck availability and supported effort in your runtime before dispatch.

| Role | Codex example | Claude example |
|---|---|---|
| Controller | Session `gpt-6.1-sol`, effort `medium` | Session `sonnet`, session effort |
| Mechanical worker | `gpt-6-luna`, supported `low` effort when sufficient | `haiku`, inherited session effort when sufficient |
| Implementation worker | `gpt-6.1-sol`, effort `medium` | `sonnet`, inherited session effort |
| Independent focused reviewer | Fresh `gpt-6.1-sol`, effort `medium` | `model: inherit` → session `sonnet`, session effort |

These examples apply the repository's capability/effort starting points. A model name alone does not establish suitability or price. Premium selection still needs task-specific evidence and any required billing authorization. Model controls and inheritance are described in the official [Codex subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [Claude subagent documentation](https://code.claude.com/docs/en/sub-agents#choose-a-model).

<details>
<summary>Codex: detailed sequence</summary>

## Codex: model and reasoning-effort selection

Model selection follows [.lean/policy/MODELS.md](../.lean/policy/MODELS.md), independently of repository mode. The main agent follows the session settings. For dispatches that the runtime can configure, start with an economical model / low effort for mechanical work, the current/default capable model / medium effort for normal implementation or focused review, and a capable model / useful high effort for hard reasoning. Budget guides optional spend and never lowers the quality floor.

```mermaid
sequenceDiagram
    actor User
    participant Agent as Codex Controller
    participant Policy as Task Contract and<br/>MODELS policy
    participant Runtime as Session and<br/>subagent runtime
    participant Record as Session evidence / tracker
    participant Subagent as Worker or fresh reviewer

    User->>Agent: Task, constraints and any explicit model preference
    Agent->>Policy: Determine capability, effort starting point, quality and budget
    Policy-->>Agent: Least costly capable option, required review depth and guards
    Agent->>Runtime: Inspect session settings and supported dispatch options
    Runtime-->>Agent: Available model/effort controls and observable metadata
    Agent->>Agent: Use current session settings for main-agent work
    Note over Agent,Runtime: Do not claim to change the main session without runtime confirmation
    opt A worker or independent reviewer is needed
        alt Mechanical work with sufficient capability
            Agent->>Agent: Choose economical capable model, supported low effort when sufficient
        else Normal implementation or focused review
            Agent->>Agent: Choose current/default capable model and supported medium effort
        else Hard reasoning
            Agent->>Agent: Choose capable available model, useful supported high effort
        end
        Note over Agent,Subagent: HIGH review requires independence, not a stronger model
        alt Supported controls and a justified selection are available
            Agent->>Agent: Prepare supported model/effort settings for dispatch
        else Selection controls unavailable
            Agent->>Agent: Use capable available defaults or inherited settings
        end
        opt Premium model is considered
            Agent->>Record: Record outcome, material constraints and cheaper-option evidence
            alt No concrete evidence that a cheaper option is insufficient
                Agent->>Agent: Use cheaper capable option, gather evidence or report constraint
            else Concrete evidence supports premium selection
                Agent->>Agent: Apply capability and budget requirements
                opt Additional paid usage would be initiated
                    Agent->>User: Request authorization for additional paid usage
                    User-->>Agent: Authorize or decline
                end
            end
        end
        Note over Agent,Subagent: Dispatch only if capability and any required billing authorization hold, otherwise BLOCKED
        Agent->>Record: Record assignment, requested settings and task-specific reason before call
        Agent->>Runtime: Dispatch worker/reviewer with selected model and effort
        Runtime->>Subagent: Resolve model/effort from supported request or defaults
        Note over Runtime,Subagent: Focused reviewer uses capable settings in a fresh context
        Runtime-->>Agent: Agent identity and reported settings if exposed
        Agent->>Record: Record reported settings, use unavailable for unexposed metadata
        Subagent-->>Agent: Diff/evidence or review verdict and findings
        opt Work fails or evidence shows quality floor is unmet
            Agent->>Agent: Classify implementation, context, tools, permissions or reasoning failure
            alt Cause is implementation, missing context, tools or permissions
                Agent->>Agent: Repair the cause rather than changing model
            else Demonstrated reasoning limit
                Agent->>Agent: Raise one supported effort level first if model remains capable
                Agent->>Agent: Consider stronger model only if still needed, reapply selection guards
            end
            Agent->>Record: Record reason and one changed variable per retry
            Note over Agent,Subagent: Review retries stay within the bounded review cycle
        end
    end
    Agent-->>User: Result with evidence or BLOCKED if required capability is unavailable
```

Requested settings are not proof of backend settings. An unsupported desired setting uses a capable available option; if none meets the quality floor, report BLOCKED. Recommend a user-controlled session change only when the current settings threaten that floor or repeated reasoning failure warrants it. Do not hardcode provider model IDs or pricing into the shared policy.

</details>

<details>
<summary>Claude: detailed sequence</summary>

## Claude: session inheritance and model selection

Claude follows the same capability, budget and premium rules. Its session model and effort come from the user's/runtime's settings. The repository's [reviewer definition](../.claude/agents/reviewer.md) has `model: inherit` and inherits session effort; runtime-supported per-invocation overrides do not require editing that shared definition.

```mermaid
sequenceDiagram
    actor User
    participant Runtime as Claude session /<br/>subagent runtime
    participant Agent as Claude Controller
    participant Policy as Task Contract and<br/>MODELS policy
    participant Record as Session evidence / tracker
    participant Subagent as Worker or fresh reviewer

    User->>Runtime: Configure session model and effort
    User->>Agent: Request task with constraints and quality expectations
    Agent->>Policy: Determine capability, effort starting point, budget and review depth
    Policy-->>Agent: Least costly capable option and required quality floor
    Agent->>Runtime: Inspect session settings and supported invocation controls
    Runtime-->>Agent: Available controls and observable settings
    Agent->>Agent: Follow session model and effort for main-agent work
    opt Worker or independent reviewer is required
        alt Mechanical work with sufficient capability
            Agent->>Agent: Choose economical capable worker with supported/inherited effort
        else Normal implementation
            Agent->>Agent: Choose capable implementation worker with supported/inherited effort
        else Independent reviewer using repository defaults
            Agent->>Agent: Use inherited session model and effort
        end
        alt Use repository reviewer defaults
            Agent->>Agent: Request inherited model and session effort
        else Justified override is supported by runtime
            Agent->>Agent: Prepare supported per-invocation model/effort selection
        else Desired override is unavailable
            Agent->>Agent: Use capable inherited/default option or report BLOCKED
        end
        Note over Agent,Subagent: Do not edit the shared reviewer definition for one task
        opt Premium model is considered
            Agent->>Record: Record outcome, material constraints and cheaper-option evidence
            alt Cheaper capable option is sufficient or insufficiency is unproven
                Agent->>Agent: Use cheaper capable option, gather evidence or report constraint
            else Concrete evidence supports premium selection
                Agent->>Agent: Apply capability and budget requirements
                opt Additional paid usage would be initiated
                    Agent->>User: Request authorization for additional paid usage
                    User-->>Agent: Authorize or decline
                end
            end
        end
        Note over Agent,Subagent: Dispatch requires capability and any required billing authorization, HIGH alone does not justify premium
        Agent->>Record: Record requested settings and task-specific selection reason before call
        Agent->>Runtime: Invoke with selected model, inherit for default reviewer
        Runtime->>Subagent: Resolve requested alias or inherit, apply supported effort
        Note over Runtime,Subagent: Default reviewer inherits settings from the session
        Note over Runtime,Subagent: Independent reviewer receives contract and diff, not author reasoning
        Runtime-->>Agent: Agent identity and reported settings if exposed
        Agent->>Record: Record actual metadata or unavailable, never infer it from request
        Subagent-->>Agent: Work evidence or PASS / REWORK with findings
        opt Failure or demonstrated reasoning limit
            Agent->>Agent: Classify cause before changing settings
            alt Implementation, context, tool or permission problem
                Agent->>Agent: Repair that cause
            else Demonstrated reasoning limit
                Agent->>Agent: Raise one supported effort level first if model remains capable
                Agent->>Agent: Consider stronger model only when needed, reapply selection guards
            end
            Agent->>Record: Record retry reason and one changed variable
            Note over Agent,Subagent: Stop at review round cap and preserve requested quality floor
        end
    end
    Agent-->>User: Evidence-backed result or BLOCKED when required capability is unavailable
```

Session inheritance does not guarantee that a configured model can meet every task's quality floor. If the runtime cannot expose or change a setting, report that limitation honestly and assess the available option against the contract. Never increase spend merely because a task is long.

</details>

## Refresh model research without switching models

Use `/lean-model-update codex`, `/lean-model-update claude` or `/lean-model-update all` to follow scope → research → grill → preview. The shared skill checks official docs and exposed runtime choices. Its default result is a diff and proposal hash. It applies only an explicitly authorized proposal, then follows the task/review/gate workflow. It never changes session models, global configuration, billing permissions or the reviewer’s `inherit` setting.

The optional `.lean/model-catalog.json` stores project-owned model/alias IDs, runtime version, efforts, lifecycle, source URLs/dates and observed availability. Public documentation alone means availability is unknown. Selected evidence older than 30 days blocks preview/apply; retained providers remain visible as stale. Missing catalog leaves normal model selection unchanged. The template ships no live catalog.

The offline CLI consumes researched JSON candidates; it does not fetch models or perform inference. Read the [catalog format](../.claude/skills/lean-model-update/references/catalog.md) before preparing a candidate. A provider refresh replaces that provider's complete model list, so review removals and aliases in the diff.

```sh
python3 .lean/scripts/model_catalog.py check
python3 .lean/scripts/model_catalog.py preview --provider codex --candidate /path/to/candidate.json
# Save the preview JSON report, review it, then apply only after authorization:
python3 .lean/scripts/model_catalog.py apply --proposal /path/to/report.json --sha256 APPROVED_PROPOSAL_DIGEST
```

Preview/check write nothing. Apply rechecks the base and evidence under a lock, preserves other providers and custom catalog fields, and writes the catalog atomically. It also creates/retains an ignored `.agent-runtime/model-catalog.lock`, including when a locked apply is refused; it never modifies runtime model settings. A changed base requires a new preview; an identical retry leaves the catalog unchanged. The proposal digest checks content consistency, not the authenticity of research. CLI failures exit 2 and do not claim a refresh succeeded. Tests use synthetic fixtures without network or paid model calls.

## Model and effort discipline

Portable policy chooses the least costly available model and supported effort capable of satisfying the task. It does not pin provider model IDs or volatile pricing. Risk, quality, repository mode, execution strategy and model choice remain separate.

Premium dispatch requires concrete evidence that a cheaper available option cannot satisfy the task; additional paid usage still needs user authorization. Agents record requested and reported settings honestly and cannot claim a runtime change that was not confirmed.
