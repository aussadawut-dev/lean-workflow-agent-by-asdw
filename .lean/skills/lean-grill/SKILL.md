---
name: lean-grill
description: Stress-test a requirement or plan before coding. Use for /lean-grill, high-risk design, or unresolved decisions on architecture, security, data, permissions, workflow behavior, integrations or acceptance.
user-invocable: true
argument-hint: "<requirement or plan>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md` (selection, handoffs and boundaries apply to every level); keep model reasoning effort separate.

# Lean Grill

Make a task ready for implementation by resolving the decisions that matter. Run a focused pass for high-risk architecture, tenant, auth, permission, data, destructive, AI/MCP write, or external-contract work even when the plan appears complete. A clear plan may finish READY without questions. Do not turn routine work into a questionnaire.

## Question depth

- **standard** — The smallest set of material questions.
- **high** — Add: walk each relevant part of the scope and ask about actors, terminology, inclusions/exclusions, rules, inputs/outputs, normal flows, boundaries, exceptions and failure/recovery behavior. Use concrete scenarios to expose missing requirements and narrow the scope.
- **ultra** — Add to high: question in multiple rounds where needed. Follow up on answers to establish conditions, exceptions, cross-flow interactions and consequences. Check answers for contradictions and confirm the boundaries of each important part before consolidating the final scope. Challenge consequential assumptions with examples, without reopening settled choices absent new evidence or conflict.

At high/ultra, group questions by topic in manageable batches and wait for answers before dependent follow-ups. Explain why each question matters, recommend an option when evidence supports it, and show the effect of alternatives. Skip categories and details already settled by the user, code or documentation.

## Workflow

1. Read the task and its closest existing context: `AGENTS.md`, `.lean/PROJECT.md`, `.lean/config.json`, and only the relevant requirement, tracker, decision, or source files. Reuse decisions already recorded; do not ask them again.
2. Identify only open choices that would materially change the result. Check the applicable boundaries: goal and acceptance, actor and user flow, data ownership and lifecycle, auth and permissions, API or external contracts, AI/MCP actions, failure behavior, and operations. Skip categories without a concrete issue.
3. Sort each open point into **NEED DECISION** or **SAFE ASSUMPTION**. A safe assumption must be low risk, reversible, consistent with known decisions, and have no security or business-rule impact. State its effect if wrong. Never assume permission semantics, tenant access, destructive behavior, retention, approval, or a breaking contract.
4. Ask the smallest set of decision questions needed to proceed, each with a recommended option and the consequence of each material alternative, then wait for the answer. If a new request conflicts with an accepted decision, name the conflict and resolve it before dependent implementation.
5. Report **READY**, **READY_WITH_ASSUMPTIONS**, or **BLOCKED** with confirmed decisions, assumptions, open decisions, and the affected acceptance criteria. `BLOCKED` applies only to the affected implementation; independent work may proceed.
6. In `tracker` or `full` mode, record accepted decisions and assumptions in the owning TCK document before implementation and update its next step. In `standard`, keep the decision summary in the conversation. Create an ADR only when the project already uses ADRs or the user requests one.

Explicit `/lean-grill` requests always get a concise readiness result. Return to `/lean-task` once the affected work is ready. This skill does not grant permission for implementation, publication, or external writes beyond the task's existing authority.

$ARGUMENTS
