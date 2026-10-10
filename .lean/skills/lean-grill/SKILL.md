---
name: lean-grill
description: Stress-test a requirement or implementation plan before coding. Use when invoked as /lean-grill, for high-risk design work, or when an unresolved decision could change architecture, security, data ownership, permissions, workflow behavior, integrations, or acceptance criteria.
user-invocable: true
argument-hint: "<requirement or plan>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

# Lean Grill

Use the decision-focused part of `grill-me` to make a task ready for implementation. Run a focused pass for high-risk architecture, tenant, auth, permission, data, destructive, AI/MCP write, or external-contract work even when the plan appears complete. A clear plan may finish READY without questions. Do not turn routine work into a questionnaire.

## Skill level

Resolve `standard`, `high`, or `ultra` under `.lean/policy/SKILL-EFFORT.md`: the user's latest task selection, saved skill override, saved default, then `standard`; the existing workflow below remains the baseline. Natural-language requests such as "scope high" or "use ultra for all three skills" are sufficient; no new runtime command is required. A request for one skill does not raise the others. Keep the selection for this work until the user changes it; a later skill-specific request overrides an earlier group request. State the effective level briefly when starting the skill. If the request is ambiguous or names an unsupported level, clarify rather than silently substituting one.

Levels are optional skill capabilities, separate from workflow mode, Task Contract quality, budget, model, execution routing and review depth. Do not change those settings or spawn agents because of a skill level. Existing risk, approval, evidence and review requirements apply at every level. Do not silently lower a requested level; report unavailable evidence or constraints explicitly.

Higher levels add relevant detail, questions and evidence; they do not expand the user's intended scope or grant implementation or external-write authority. Reuse confirmed decisions. When handing off to scope, research or grill, preserve any user-selected level for the destination skill; otherwise resolve its saved override/default under SKILL-EFFORT. Feed findings back into the scope and decision summary, reopening only decisions affected by new evidence or a material conflict. In tracker/full mode, keep levels and findings in the existing owning tracker; in standard mode, keep them in the conversation.

### Question depth

- **standard** — Use the existing focused decision workflow below, asking the smallest set of material questions.
- **high** — Add to standard: walk each relevant part of the scope and ask more questions about actors, terminology, inclusions/exclusions, rules, inputs/outputs, normal flows, boundaries, exceptions and failure/recovery behavior. Use concrete scenarios to expose missing requirements and narrow the scope. Ask about details needed for precise acceptance even when they are not architectural decisions.
- **ultra** — Add to high: question in multiple rounds where needed. Follow up on answers to establish conditions, exceptions, cross-flow interactions and consequences. Walk relevant edge/failure scenarios, check answers for contradictions and confirm the boundaries of each important part before consolidating the final scope. Challenge consequential assumptions with examples, without reopening settled choices absent new evidence or conflict.

At high/ultra, group questions by topic in manageable batches; wait for answers before dependent follow-ups. Explain why each question matters, recommend an option when evidence supports it, and show the effect of alternatives. Ask more because the scope needs precision, not to meet a question quota. Skip irrelevant categories and details already settled by the user, code or documentation. A precise existing scope may need no further questions even at ultra. Keep confirmed answers and remaining questions together; feed them back to scope. Stop when the important parts are precise enough to define acceptance, or report the affected work BLOCKED with the remaining decisions. For high/ultra, apply the depth rules above when identifying open points and choosing questions in the numbered workflow; its standard minimal-question guidance must not omit details needed for precise scope. Preserve NEED DECISION/SAFE ASSUMPTION and readiness reporting below.

1. Read the task and its closest existing context: `AGENTS.md`, `.lean/PROJECT.md`, `.lean/config.json`, and only the relevant requirement, tracker, decision, or source files. Reuse decisions already recorded; do not ask them again.
2. Identify only open choices that would materially change the result. Check the applicable boundaries: goal and acceptance, actor and user flow, data ownership and lifecycle, auth and permissions, API or external contracts, AI/MCP actions, failure behavior, and operations. Skip categories without a concrete issue.
3. Sort each open point into **NEED DECISION** or **SAFE ASSUMPTION**. A safe assumption must be low risk, reversible, consistent with known decisions, and have no security or business-rule impact. State its effect if wrong. Never assume permission semantics, tenant access, destructive behavior, retention, approval, or a breaking contract.
4. Ask the smallest set of decision questions needed to proceed. Group tightly related choices, give a recommended option and the consequence of each material alternative, then wait for the answer. Do not ask about details that code or existing documentation already settles. If a new request conflicts with an accepted decision, name the conflict and resolve it before dependent implementation.
5. Report **READY**, **READY_WITH_ASSUMPTIONS**, or **BLOCKED** with confirmed decisions, assumptions, open decisions, and the affected acceptance criteria. `BLOCKED` applies only to the affected implementation; independent work may proceed. Do not start dependent code while a material decision remains open.
6. In `tracker` or `full` mode, locate or create the owning TCK document, record accepted decisions and assumptions there before implementation, and update its next step. In `standard`, keep the decision summary in the conversation. Create an ADR only when the project already uses ADRs or the user requests one.

Explicit `/lean-grill` requests always get a concise readiness result, even when no question is needed. Return to `/lean-task` once the affected work is ready. This skill does not grant permission for implementation, publication, or external writes beyond the task's existing authority.

$ARGUMENTS
