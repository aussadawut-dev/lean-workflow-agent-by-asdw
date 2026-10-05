---
name: lean-grill
description: Stress-test a requirement or implementation plan before coding. Use when invoked as /lean-grill, for high-risk design work, or when an unresolved decision could change architecture, security, data ownership, permissions, workflow behavior, integrations, or acceptance criteria.
---

# Lean Grill

Use the decision-focused part of `grill-me` to make a task ready for implementation. Run a focused pass for high-risk architecture, tenant, auth, permission, data, destructive, AI/MCP write, or external-contract work even when the plan appears complete. A clear plan may finish READY without questions. Do not turn routine work into a questionnaire.

1. Read the task and its closest existing context: `AGENTS.md`, `.lean/PROJECT.md`, `.lean/config.json`, and only the relevant requirement, tracker, decision, or source files. Reuse decisions already recorded; do not ask them again.
2. Identify only open choices that would materially change the result. Check the applicable boundaries: goal and acceptance, actor and user flow, data ownership and lifecycle, auth and permissions, API or external contracts, AI/MCP actions, failure behavior, and operations. Skip categories without a concrete issue.
3. Sort each open point into **NEED DECISION** or **SAFE ASSUMPTION**. A safe assumption must be low risk, reversible, consistent with known decisions, and have no security or business-rule impact. State its effect if wrong. Never assume permission semantics, tenant access, destructive behavior, retention, approval, or a breaking contract.
4. Ask the smallest set of decision questions needed to proceed. Group tightly related choices, give a recommended option and the consequence of each material alternative, then wait for the answer. Do not ask about details that code or existing documentation already settles. If a new request conflicts with an accepted decision, name the conflict and resolve it before dependent implementation.
5. Report **READY**, **READY_WITH_ASSUMPTIONS**, or **BLOCKED** with confirmed decisions, assumptions, open decisions, and the affected acceptance criteria. `BLOCKED` applies only to the affected implementation; independent work may proceed. Do not start dependent code while a material decision remains open.
6. In `tracker` or `full` mode, locate or create the owning TCK document, record accepted decisions and assumptions there before implementation, and update its next step. In `standard`, keep the decision summary in the conversation. Create an ADR only when the project already uses ADRs or the user requests one.

Explicit `/lean-grill` requests always get a concise readiness result, even when no question is needed. Return to `/lean-task` once the affected work is ready. This skill does not grant permission for implementation, publication, or external writes beyond the task's existing authority.

$ARGUMENTS
