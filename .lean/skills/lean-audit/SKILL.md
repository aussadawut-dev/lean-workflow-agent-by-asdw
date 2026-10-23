---
name: lean-audit
description: Audit an existing area against accepted scope and standards with evidenced findings; shipping-diff review is lean-review.
user-invocable: true
argument-hint: "<area and accepted scope/standards to audit>"
---

# Lean Audit

Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity. Inspect an existing area against accepted requirements; shipping-diff review belongs to `lean-review`. This procedure adds no gate, scheduled audit or automatic remediation.

## Bound the audit

Read PROJECT, requested scope, applicable standards and accepted exceptions under `.lean/policy/CONTEXT.md`. For submodules resolve `python3 .lean/scripts/submodule.py context`: code/checks in `project_root`, records in `record_root`, shared resources in `workflow_root`. Reuse the owning tracker in tracker/full; otherwise report in conversation unless saving is authorized. Create no extra workset or queue items.

State area, exclusions, baseline IDs/versions and inspected revision/working state. More specific accepted exceptions apply within their limits. Conflicting baselines with unclear precedence need Grill; continue independently settled areas. Without an accepted baseline, report the gap: `lean-pattern` may propose one, but new best practices are not retroactive requirements or proof of a defect.

## Gather and classify evidence

1. Trace applicable requirements through relevant source/dependencies and available tests/runtime evidence. Use existing safe checks and respect gate-mode authorization. No destructive checks, production writes or new test infrastructure are authorized. Static code cannot establish visual, keyboard or live-integration behavior: mark missing verification explicitly and disclose sampling.
2. Select checks by baseline and area:
   - **Structure:** placement, module boundary, dependency direction and duplicates. Legacy moves affecting imports/builds/entrypoints need `NEEDS_DECISION` and `lean-grill` before remediation.
   - **i18n:** hardcoded user-facing strings, missing/orphan keys, placeholder parity, concatenation/pluralization, per-locale grammar and natural phrasing, terminology/glossary and tone. Uncertain legacy/domain wording or UX meaning needs Grill before edits.
3. Classify with evidence:

   | Result | Condition |
   |---|---|
   | `CONFORMS` | Applicable requirement verified within stated coverage |
   | `DEVIATION` | Accepted applicable requirement conflicts with evidence |
   | `ACCEPTED_EXCEPTION` | Matching approval reference and bounded applicability |
   | `NEEDS_DECISION` | Material intent/precedence remains unresolved |
   | `UNVERIFIED` | Required evidence unavailable |
   | `IMPROVEMENT` | New recommendation or unmet advisory rule |

   Unmet `recommended` rules are nonblocking `IMPROVEMENT` unless explicitly promoted by accepted scope/decision. Importance alone never promotes them; report independent mandatory violations separately.
4. Before questioning uncertain differences, inspect decisions, tests, comments and relevant history. Reuse valid exceptions; do not attribute motives. Grill consequential unresolved behavior/contracts before remediation. Use [the finding format](../../templates/audit-finding.md): requirement, location, evidence, impact/priority, uncertainty, action/dependencies and verification. Merge symptoms sharing a root cause while retaining locations; avoid unsupported style findings.

## Report and handoff

Report baseline/state, coverage/sampling, findings by priority, exceptions, pending decisions and unrun checks. No deviations means only none found within coverage; classifications are not review verdicts/receipts, gate passes or evidence of unperformed work.

Recommend bounded remediation and checks without editing code, hiding findings through changed standards, creating backlog or declaring fixes complete. After Grill, use a two-track handoff: (1) explicitly user-approved standard, compound/domain term precedence or bounded exception records in `record_root` (never self-grant exceptions or weaken mandatory rules to hide findings); (2) authorized remediation through `lean-scope` / `lean-task`, tests, review and gate, separating LOW/MEDIUM copy fixes from HIGH boundary/entrypoint refactors. Preserve resolved decisions in existing records.

Use delta context for re-audits: retain valid baseline/evidence, inspect changed paths and affected dependencies; refresh runtime evidence when facts may have changed. Stop when each requested requirement is evidenced or explicitly unverified/pending and coverage limits are clear. Normal completion rules still apply to the audit itself.

## Intensity

- **standard:** trace the bounded baseline and report findings/limits.
- **high:** follow callers, dependencies, failure paths and remediation interactions.
- **ultra:** challenge consequential cross-area invariants, contradictory evidence and migration/recovery within scope; no automatic expansion or unsupported passes.

For skill evaluation only, use [the scenario guide](references/scenarios.md). Do not load/run it during ordinary audits. Instruction tests do not prove agent behavior.

$ARGUMENTS
