---
name: lean-pattern
description: Propose or maintain project standards with evidence and accepted exceptions; for conventions shared across tasks, not one feature or diff.
user-invocable: true
argument-hint: "<project area or standard to define/update>"
---

# Lean Pattern

Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity. Define standards shared across tasks; use scope for one feature. This optional procedure adds no gate or automatic audit.

## Establish context

Bound the requested area. Read PROJECT, applicable standards/decisions and relevant source under `.lean/policy/CONTEXT.md`. For submodules, resolve `python3 .lean/scripts/submodule.py context`: code in `project_root`, project records in `record_root`, shared tools/templates in `workflow_root`. Reuse document locations and the owning tracker in tracker/full; standard proposals may stay in conversation until saving is authorized. Keep PROJECT a short map.

Establish an early baseline on new projects. On existing repositories inspect layouts, call paths and copy before proposing disruptive structure or terminology changes; resolve material trade-offs through `lean-grill`. Observed consistency alone proves neither acceptance nor suitability.

Select relevant topics, not a mandatory catalog or universal stack/layout:

- **Repository structure and module boundaries:** directory roles, dependency direction and homes for tests, schemas/types, configuration and locales, based on the actual stack.
- **i18n and language:** no hardcoded user-facing strings; locale key parity; interpolation/pluralization rather than variable concatenation; per-locale grammar and natural phrasing, terminology/glossary, tone/politeness and compound/domain term precedence over general single-word glossaries.
- Other requested areas may include UX/UI, accessibility, API/data, security, tests, reliability or operations. Do not invent standards for absent areas.

## Propose standards

1. Reuse accepted decisions. Research only meaningful alternatives or evidence gaps; best-practice requests need authoritative, stack/version-appropriate sources. Compare the current approach and migration/maintenance costs. Record sources, dates/versions and uncertainty; do not repeat unchanged research.
2. Adapt [the project-standard format](../../templates/project-standard.md): stable ID, observable rule, applicability, mandatory/recommended strength, rationale, evidence, verification, decision status and bounded exceptions. `recommended` is advisory; promotion to mandatory needs explicit accepted scope/decision.
3. Search decisions/history before Grill for material conflicts, uncertain intent or unresolved choices. Do not infer intent from unusual code; continue independently settled work while answers are pending.
4. Show the delta and its effect. New/changed rules and exceptions stay `proposed` until matching approval. Record acceptance reference/version; keep superseded decisions `deprecated` with replacement links. Do not rewrite historical acceptance or apply new standards retroactively; migrations need explicit scope.

## Handoff

Report area, kept/proposed/changed standards, evidence, exceptions, open choices and verification. Save only authorized records; templates contain no project approvals. Recommendations authorize no fixes, backlog or publication. Approved remediation uses `lean-scope` / `lean-task`; requested baseline inspection uses `lean-audit`.

For fast deterministic checks of accepted `mandatory` rules, propose PROJECT gate integration through `/lean-scope` and `accept-controls`. On existing repositories use a ratchet/baseline or changed-scope filter. Never gate `recommended` rules or silently edit controls; existing review/gate-mode rules apply.

Use delta context on feedback: reread changed rules and affected dependencies, retaining valid decisions/evidence. Stop when the bounded proposal has observable verification and each material choice is accepted or explicitly pending; do not add unrelated categories.

## Intensity

- **standard:** bounded rules, evidence, applicability and decisions.
- **high:** trace dependencies/failures and verify usable checks and compatible exceptions.
- **ultra:** challenge consequential cross-area assumptions, migration/recovery and contradictory evidence within scope; no category or research quotas.

$ARGUMENTS
