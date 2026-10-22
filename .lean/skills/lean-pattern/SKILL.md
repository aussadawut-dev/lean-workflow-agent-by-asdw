---
name: lean-pattern
description: Propose or maintain project standards with evidence and accepted exceptions; for conventions shared across tasks, not one feature or diff.
user-invocable: true
argument-hint: "<project area or standard to define/update>"
---

# Lean Pattern

Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity. This optional procedure uses existing research, scope and Grill; it adds no gate or automatic audit.

## Establish context

Read PROJECT and the relevant existing standards, accepted decisions and source. For a submodule, resolve `python3 .lean/scripts/submodule.py context`: inspect code in `project_root`, keep project standards and findings in `record_root`, and use shared procedures/templates from `workflow_root`. Reuse existing document locations and keep PROJECT a short map linking to them. In tracker/full mode use the owning workset; in standard mode a proposal may remain in the conversation until saving is requested or included in approved scope.

Bound the work to the requested area. Identify the actual stack, constraints and existing conventions, distinguishing greenfield/early baseline setup from existing repositories:

- **Greenfield or early-stage projects:** establish an early baseline up front so subsequent features follow one convention without large rework.
- **Existing repositories:** inspect current layouts, call paths and copy first, separate working conventions from defects, and ask through `lean-grill` before proposing disruptive structural moves or terminology rewrites.

Select applicable topics, such as repository/module boundaries, code conventions, UX flows, UI components/tokens, accessibility, i18n, API contracts, data, security/privacy, tests, performance/reliability or operations. These are prompts for selection, not a required catalog. Do not prescribe an application stack, universal folder tree or design system, or manufacture standards for absent areas:

- **Repository structure and module boundaries:** define stack-appropriate directory roles, module boundaries, dependency direction (which layers or features may import each other), and standard homes for tests, schemas/types, configurations and locale assets based on the project's actual stack rather than a single universal folder tree.
- **i18n and per-locale language standards:** when the project has user-facing copy or multiple locales, cover both technical i18n hygiene (no hardcoded user-facing strings, locale key parity across supported languages, and interpolation/pluralization instead of string concatenation across variables) and per-locale linguistic quality (correct grammar and natural phrasing for each language rather than literal word-for-word translation, shared terminology/glossary consistency across screens, and consistent tone/politeness level).

## Propose standards

1. Distinguish observed conventions from accepted requirements. Reuse valid decisions and evidence; consistency alone does not prove a convention was approved or is suitable.
2. Use `lean-research` when meaningful alternatives or missing evidence could change the recommendation. For a best-practice request, research authoritative sources appropriate to the stack and supported versions. Compare keeping the current approach with relevant alternatives, including migration/maintenance cost. Record source/version or date and uncertainty; do not browse again merely to restate an unchanged accepted choice.
3. Describe rules using [the project-standard format](../../templates/project-standard.md), adapting it to existing project documentation. Each needs a stable ID, observable rule, applicability, mandatory/recommended strength, rationale, evidence, verification and decision status. Include accepted exceptions and their limits. Keep rules small enough to audit; avoid vague claims such as "use good UX."
   `recommended` is advisory and does not block work. An explicit accepted scope/decision may promote a rule to mandatory for its stated area; record that change and approval rather than silently escalating a recommendation.
4. Use `lean-grill` for material conflicts or unresolved choices, including differences that may preserve intentional behavior. Search decisions and relevant history before asking. Do not infer intent from unusual code alone. Resolve only the affected choice; continue independent analysis.
5. Present the proposed delta and its effect on existing work. New or changed standards and exceptions remain `proposed` until matching approval. Reuse prior approval without asking again. Record acceptance with its reference and version; retain superseded decisions as `deprecated` with a replacement link where applicable. Do not rewrite old acceptance evidence or silently apply a new standard retroactively; make any migration scope explicit through `lean-scope`.

## Handoff

Report the selected area, standards kept/proposed/changed, evidence, accepted exceptions, open decisions and validation paths. Save approved records only within authorized scope and route them from PROJECT when needed. Standards and decisions are project-owned; templates contain no project approvals. Do not create application fixes, backlog items or publication actions from recommendations without matching authorization. Approved remediation follows `lean-scope` / `lean-task`; `lean-audit` can check the accepted baseline when requested. Existing review, gate and project gate-mode requirements remain in force.

## Intensity

- **standard:** bounded rules and evidence for the selected area, with explicit applicability and decisions.
- **high:** trace relevant dependencies and failure cases; check that each rule has a usable verification path and exceptions do not conflict.
- **ultra:** challenge consequential assumptions across affected areas, migration/recovery implications and contradictory evidence. Stop at the agreed boundary; do not add categories or research quotas just for intensity.

$ARGUMENTS
