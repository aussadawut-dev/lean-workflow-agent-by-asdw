# Skills and procedure intensity

[Back to README](../README.md)

Run CLI examples from the repository root.

## Core and optional commands

All nine core procedures are user-invocable, including `lean-skill-effort`; the ten optional commands require the optional pack. Start ordinary work with `lean-task`; the agent handles scope, research, material decisions, implementation, review and completion checks as needed. It asks for unresolved material decisions or new scope approval, and preserves accepted decisions. You do not need to run each internal step yourself.

| Purpose | Discovery | Claude Code | Codex skill invocation |
|---|---|---|---|
| Set up mode and execution | Core | `/lean-init [standard\|tracker\|full] [--execution direct\|delegated]` | `$lean-init` with the same arguments |
| Start a task | Core | `/lean-task <task description>` | `$lean-task <task description>` |
| Define or amend scope | Core | `/lean-scope <requirement or scope amendment>` | `$lean-scope` with the same arguments |
| Compare approaches with evidence | Core | `/lean-research <research question>` | `$lean-research` with the same arguments |
| Stress-test requirements or a plan | Core | `/lean-grill <requirement or plan>` | `$lean-grill` with the same arguments |
| Review changes | Core | `/lean-review [diff or scope]` | `$lean-review` with the same arguments |
| Verify completion | Core | `/lean-gate [task or workset]` | `$lean-gate` with the same arguments |
| Coordinate delegated work | Core | `/lean-multi-agent <bounded delegation task>` | `$lean-multi-agent` with the same arguments |
| Set procedure intensity | Core | `/lean-skill-effort [standard\|high\|ultra\|reset] [lean-skill-name]` | `$lean-skill-effort` with the same arguments |
| Inspect or set gate automation | Optional | `/lean-quality-gate-mode [auto\|manual]` | `$lean-quality-gate-mode` with the same arguments |
| Define or maintain project standards | Optional | `/lean-pattern <area>` | `$lean-pattern <area>` |
| Audit accepted scope and standards | Optional | `/lean-audit <area and baseline>` | `$lean-audit` with the same arguments |
| Research a model catalog refresh | Optional | `/lean-model-update [codex\|claude\|all]` | `$lean-model-update` with the same arguments |
| Audit and shorten workflow prose | Optional | `/lean-compress [workflow\|PATH...] [--preview\|--apply]` | `$lean-compress` with the same arguments |
| Use an application submodule | Optional | `/lean-use-submodule <remote url>` | `$lean-use-submodule <remote url>` |
| Take over an existing workflow | Optional | `/lean-takeover-workflow "<target path>" [--preview\|--apply <plan-id>]` | `$lean-takeover-workflow` with the same arguments |
| Archive completed queue items | Optional | `/lean-clean-queue <old\|all> [--preview]` | `$lean-clean-queue` with the same arguments |
| Update installed Lean workflow | Optional | `/lean-update-workflow [--ref <ref>]` | `$lean-update-workflow` with the same arguments |
| Audit and clean repository files | Optional | `/lean-clean-repo [--path <path>]` | `$lean-clean-repo` with the same arguments |

For example:

```text
# Claude Code
/lean-task Add a regression test and fix the queue lease bug
/lean-compress workflow --preview
/lean-clean-queue old --preview

# Codex
$lean-task Add a regression test and fix the queue lease bug
$lean-compress workflow --preview
$lean-clean-queue old --preview
```

All discovered Lean skills are user-invocable and remain available to the agent, including scope, research, grill, review, gate and multi-agent. Nine core skills are discovered by default; enabling the optional pack exposes ten more. Command visibility does not change scope approval or execution routing.

In Codex CLI/IDE, select skills through `/skills` or mention them with `$`; use the available skill picker in Desktop. Keep implicit invocation enabled so the agent can follow the shared procedures. Examples elsewhere using `/name` describe Claude syntax; use the corresponding Codex skill invocation. No deprecated custom prompts or global installation are required. See [Claude skill invocation](https://code.claude.com/docs/en/skills) and [Codex skill invocation](https://learn.chatgpt.com/docs/build-skills).

Model refresh and compression still preview by default; applying a catalog proposal or compression requires its existing authorization checks. Queue cleanup with `old` or `all` authorizes archiving DONE items; `--preview` only shows the selection. Missing queue selection requires a choice. Command visibility grants no extra permissions, paid usage or Git publishing.

## Project standards and conformance audits

`lean-pattern` turns relevant research and accepted decisions into project standards that later tasks can reference. Select only applicable areas: repository boundaries, UX/UI components, accessibility, i18n, API/data, security, testing or operations. It preserves existing conventions where appropriate and proposes changes with applicability, mandatory/recommended strength, verification and explicit approval. Use the [standard record format](../.lean/templates/project-standard.md) within existing project documents; PROJECT remains a short map. A newly researched practice remains a proposal until accepted, with migration scoped separately. Recommended rules are advisory and never block work unless an accepted scope explicitly promotes them to mandatory.

`lean-audit` checks a requested area against accepted scope, standards and exceptions, including existing code beyond a shipping diff. Its [report format](../.lean/templates/audit-finding.md) separates evidenced deviations, accepted exceptions, unresolved decisions, missing verification and improvement suggestions. When a difference may be intentional, inspect decisions/history first and use Grill before consequential remediation. Report sampling and runtime evidence gaps; a static inspection cannot establish visual or live behavior. A missing baseline is a gap, not permission to impose a new one.

Both procedures use existing scope/research/Grill/task handoffs, submodule record routing and project gate policy. They add no automatic audits or gate requirements and do not replace diff review, validation or acceptance. Output stays in the conversation unless saving is requested or approved; findings do not create a backlog or authorize fixes automatically. The optional pack remains disabled by default.

```text
/lean-pattern i18n conventions for the existing web app
$lean-audit settings forms against accepted UX and i18n standards
```

## Optional skill levels

All Lean procedures support `standard` (the existing default), `high` and `ultra` intensity under [.lean/policy/SKILL-EFFORT.md](../.lean/policy/SKILL-EFFORT.md). Ask in natural language, for example: "use scope high, grill ultra and research high for this task" or "use ultra for all three skills". Task-specific requests remain in the task. Use `/lean-skill-effort high` to save a default, `/lean-skill-effort ultra lean-research` for an override, and `reset` to remove saved choices. No arguments inspects without writes. Settings are optional project-owned data, preserved on upgrades and kept in the selected target record root. Levels can differ per skill, and do not change workflow mode, quality, budget, model, execution or review requirements.

Effective intensity follows the latest explicit task selection, then the saved skill override, saved default and finally `standard`. Setting a global level clears saved overrides. Resetting one skill restores inheritance; resetting globally removes the settings file. Invalid settings are reported without silently repairing them.

Use the shared CLI directly when working without an agent:

```sh
python3 .lean/scripts/skill_effort.py                      # Inspect; no writes
python3 .lean/scripts/skill_effort.py high                 # Save the global default
python3 .lean/scripts/skill_effort.py ultra lean-research  # Save a named override
python3 .lean/scripts/skill_effort.py reset lean-research  # Inherit the global default
python3 .lean/scripts/skill_effort.py reset                # Return all skills to standard
```

These write commands change only project procedure preferences in `.lean/skill-effort.json`. With an active submodule, they use its record root; add `--root <record-root>` before the level for an explicit override. An invalid selected-target context blocks instead of falling back to Lean's own records. No preferences file is shipped by default.

| Skill | high adds to standard | ultra adds to high |
|---|---|---|
| Scope | Detailed flows, rules, boundaries and acceptance per behavior | Material states, exceptions, failures and cross-flow consistency, with traceable validation |
| Grill | More questions by scope topic to find omissions and narrow requirements | Follow-up rounds, scenario details and confirmation of each important boundary |
| Research | More relevant vendors/approaches and corroborated decisive claims | Broader discovery, deeper comparison of leading candidates and conditional conclusions |
| Review | Trace callers, interfaces and relevant failure paths | Challenge consequential assumptions and cross-component invariants |
| Pattern | Trace rule dependencies, verification and exceptions | Challenge cross-area assumptions and migration implications |
| Audit | Follow callers and failure paths; cross-check findings | Challenge cross-area invariants and contradictory evidence within scope |
| Gate | Map acceptance criteria to current evidence and expose stale coverage | Cross-check scope, tests, review, tracker and queue consistency |

Higher levels reuse confirmed decisions and focus on relevant details. Grill asks in manageable batches; research distinguishes vendor breadth from source depth and reports evidence gaps. Findings can feed back into the scope, while approval and authority boundaries stay in force. These instructions guide agent behavior; repository checks validate the instruction contracts, not the accuracy of every future agent response.
