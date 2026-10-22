# Skills and procedure intensity

[Back to README](../README.md)

Run the CLI examples from the repository root.

## Core and optional commands

For everyday work, start with `lean-task`. It brings in scope, research, important decisions, implementation, review and completion checks as the task needs them. You can call any discovered skill yourself too. You do not need to walk through every step manually.

Nine core skills are available by default. Enable the optional pack to discover the other eight, then reload your runtime's skills.

| What you want to do | Pack | Claude Code | Codex |
|---|---|---|---|
| Set up mode and execution | Core | `/lean-init [standard\|tracker\|full] [--execution direct\|delegated]` | `$lean-init` with the same arguments |
| Start a task | Core | `/lean-task <task description>` | `$lean-task <task description>` |
| Define or change scope | Core | `/lean-scope <requirement or scope amendment>` | `$lean-scope` with the same arguments |
| Research and compare options | Core | `/lean-research <question>` | `$lean-research` with the same arguments |
| Find gaps in a requirement or plan | Core | `/lean-grill <requirement or plan>` | `$lean-grill` with the same arguments |
| Review changes | Core | `/lean-review [diff or scope]` | `$lean-review` with the same arguments |
| Check completion | Core | `/lean-gate [task or workset]` | `$lean-gate` with the same arguments |
| Coordinate delegated work | Core | `/lean-agents <bounded task>` | `$lean-agents` with the same arguments |
| Set procedure intensity | Core | `/lean-effort [standard\|high\|ultra\|reset] [lean-skill-name]` | `$lean-effort` with the same arguments |
| Define project standards | Optional | `/lean-pattern <area>` | `$lean-pattern <area>` |
| Audit accepted scope and standards | Optional | `/lean-audit <area and baseline>` | `$lean-audit` with the same arguments |
| Research a model catalog update | Optional | `/lean-catalog [codex\|claude\|all]` | `$lean-catalog` with the same arguments |
| Shorten workflow prose | Optional | `/lean-compress [workflow\|PATH...] [--preview\|--apply]` | `$lean-compress` with the same arguments |
| Add an application submodule | Optional | `/lean-target <remote url>` | `$lean-target <remote url>` |
| Migrate an existing workflow | Optional | `/lean-takeover "<target path>" [--preview\|--apply <plan-id>]` | `$lean-takeover` with the same arguments |
| Archive completed queue items or clean repository files | Optional | `/lean-prune queue <old\|all> [--days N] [--preview]` or `/lean-prune repo [--path <path>]` | `$lean-prune` with the same arguments |
| Update installed Lean files | Optional | `/lean-update [--ref <ref>]` | `$lean-update` with the same arguments |

For example:

```text
# Claude Code
/lean-task Add a regression test and fix the queue lease bug
/lean-compress workflow --preview
/lean-prune queue old --preview

# Codex
$lean-task Add a regression test and fix the queue lease bug
$lean-compress workflow --preview
$lean-prune queue old --preview
```

In Codex, use `$skill-name` or the runtime's skill picker. Keep implicit invocation enabled so the agent can use the shared procedures when needed. Examples using `/name` elsewhere are Claude syntax. There is no need to install deprecated custom prompts or copy skills into a global directory.

Discovery makes a skill available. Accepted scope and execution routing still decide what the agent may do. Model research, repository cleanup and compression preview by default; applying their proposals follows their approval checks. Queue archival with `queue old` or `queue all` authorizes archiving the selected DONE items, while `--preview` only shows them. With no selection, the agent asks which target (`queue` or `repo`) you want. Skills do not grant extra permissions, paid usage or Git publishing.

## Project standards and conformance audits

Use `lean-pattern` when you want research and accepted decisions turned into project standards. Choose the relevant area: repository structure and module boundaries, UX/UI, accessibility, i18n and per-locale language quality (grammar, natural phrasing, terminology/glossary and tone), API/data, security, testing or operations. On new projects, define these baselines early after `/lean-init` so feature work stays consistent without large rework; on existing repositories, inspect current conventions first and resolve material trade-offs through `lean-grill` before proposing disruptive changes.

It keeps suitable existing conventions and proposes changes with a clear use case, mandatory/recommended strength, verification and approval. Use the [standard record format](../.lean/templates/project-standard.md) in existing project documents. Keep PROJECT as a short map. New research stays a proposal until accepted; migration has its own scope. Recommended rules stay advisory unless accepted scope makes them mandatory.

Use `lean-audit` to check an area against accepted scope, standards and exceptions, including existing code beyond the current diff (such as module boundary violations, hardcoded user-facing strings, missing locale keys, unnatural literal translations, or inconsistent terminology/grammar across languages). The [finding format](../.lean/templates/audit-finding.md) separates confirmed deviations, accepted exceptions, open decisions, missing verification and suggestions.

If a difference might be intentional, inspect decisions and history first. Use Grill before a fix that could change important behavior. State what was sampled and what runtime evidence is missing. Static reading cannot prove how a screen looks or how a live system behaves. A missing baseline is a gap to resolve.

Both skills use the existing scope/research/Grill/task handoffs, submodule record routing and gate policy. They add no automatic audits or gate requirements. Results stay in the conversation unless saving is requested or approved. Findings do not automatically create a backlog or authorize fixes.

```text
/lean-pattern i18n conventions for the existing web app
$lean-audit settings forms against accepted UX and i18n standards
```

## Optional skill levels

Every Lean procedure supports `standard`, `high` and `ultra`. Standard is the default. Higher levels add relevant detail to that skill's procedure under [.lean/policy/SKILL-EFFORT.md](../.lean/policy/SKILL-EFFORT.md).

For one task, say “use scope high, grill ultra and research high for this task.” To save preferences, use `lean-effort`. No arguments just shows the settings.

The order is: latest explicit choice for the task → saved skill override → saved default → `standard`. Setting a global level clears individual overrides. Resetting one skill restores inheritance; resetting all removes the settings file. Invalid settings are reported rather than silently repaired.

You can also use the CLI:

```sh
python3 .lean/scripts/skill_effort.py                      # Inspect; no writes
python3 .lean/scripts/skill_effort.py high                 # Save the default
python3 .lean/scripts/skill_effort.py ultra lean-research  # Set research separately
python3 .lean/scripts/skill_effort.py reset lean-research  # Inherit the default
python3 .lean/scripts/skill_effort.py reset                # Reset all to standard
```

Saved preferences live in project-owned `.lean/skill-effort.json` and survive upgrades. With an active submodule, these commands use its record root; put `--root <record-root>` before the level to select another root explicitly. Invalid target context blocks the command. The template ships no preference file.

| Skill | What high adds | What ultra adds to high |
|---|---|---|
| Scope | More detail on flows, rules, boundaries and acceptance | Important states, exceptions, failures and consistency between flows |
| Grill | Walk through relevant topics and failure scenarios | Follow up on answers and check important interactions |
| Research | Compare more relevant approaches and check decisive claims | Investigate leading options more deeply, including conflicting evidence |
| Review | Trace callers, interfaces and failure paths | Challenge important assumptions and invariants across components |
| Pattern | Trace rule dependencies, verification and exceptions | Check assumptions across areas and migration implications |
| Audit | Follow callers and failure paths; cross-check findings | Check invariants and conflicting evidence across the requested area |
| Gate | Match acceptance criteria to current evidence | Check consistency across scope, tests, review, tracker and queue |

Higher intensity keeps confirmed decisions and focuses on useful detail. Grill asks in manageable batches. Research distinguishes the number of options from the depth of evidence. Levels do not change model reasoning effort, quality, budget, workflow mode, execution or review requirements, and do not activate more skills by themselves.

These procedures guide the agent. Repository checks validate the instruction contracts; they cannot guarantee every future agent response is correct.
