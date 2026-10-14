---
name: lean-audit
description: Audit a bounded project area against accepted scope, standards and exceptions, reporting evidenced remediation findings. Use for existing-system conformance beyond a shipping diff; ordinary change review remains lean-review.
user-invocable: true
argument-hint: "<area and accepted scope/standards to audit>"
---

# Lean Audit

Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity. This optional procedure reports findings; it adds no gate, scheduled audit or automatic remediation.

## Bound the audit

Read PROJECT, the requested scope/acceptance, applicable standards and accepted exceptions. Resolve submodule roots with `python3 .lean/scripts/submodule.py context` when applicable: inspect source and run relevant safe checks in `project_root`, keep authorized project records in `record_root`, and use procedures/templates in `workflow_root`. Reuse the owning tracker in tracker/full mode; in standard mode report in the conversation unless saving is requested or approved. Do not create a second workset or queue items merely to audit.

State the area, exclusions, baseline IDs/versions and source revision or working-tree state. Respect more specific accepted exceptions within their limits. If accepted documents conflict and precedence is unclear, send the affected decision to `lean-grill` rather than inventing precedence. Audit other independently settled areas meanwhile.

If no accepted baseline exists, report that gap. `lean-pattern` may propose one, but newly researched best practices are recommendations, not retroactive requirements. Missing acceptance evidence is a verification gap; it is not by itself proof the implementation is wrong.

## Gather and classify evidence

1. Trace each applicable requirement to implementation and available tests/runtime evidence. Inspect relevant dependencies rather than assuming folder boundaries define behavior. Use existing checks appropriate to the area; report unrun checks and follow project gate-mode/authorization rules for a full gate. An audit does not authorize destructive checks, production writes or a new test infrastructure.
2. Verify findings against actual source and behavior where possible. Separate observed behavior from inference. Static code cannot establish visual fidelity, keyboard usability or a live integration result; use relevant runtime evidence or mark those claims unverified. Report sampling boundaries and never generalize a sample into a whole-system pass.
3. Classify each result: `CONFORMS`, `DEVIATION`, `ACCEPTED_EXCEPTION`, `NEEDS_DECISION`, `UNVERIFIED`, or `IMPROVEMENT`. A `DEVIATION` needs an applicable accepted requirement and conflicting evidence. A suggested new best practice is `IMPROVEMENT`. An exception needs its approval reference and applicable limits.
   Respect rule strength: an unmet `recommended` rule is `IMPROVEMENT` and does not block work. Only an accepted scope/decision that explicitly makes it mandatory can make nonconformance blocking. Do not elevate strength because a recommendation looks important; report a concrete independent mandatory violation separately with its own evidence.
4. When a difference may be intentional, first inspect relevant decisions, tests, comments and history. If intent remains uncertain and changing it could alter behavior, contracts or an accepted decision, mark `NEEDS_DECISION` and use `lean-grill` before remediation. Present the evidence, consequences and options without attributing motives. Do not ask again about a valid accepted exception. Continue independent audit work while the affected decision is pending.
5. Use [the audit-finding format](../../templates/audit-finding.md): requirement, location, observed evidence, impact/priority, confidence or uncertainty, proposed action, dependencies and verification. Merge duplicate symptoms that have the same root cause while retaining affected locations. Do not inflate findings with unsupported style preferences.

## Report and handoff

Report the baseline and inspected state, coverage (including sampling/exclusions), findings by priority, accepted exceptions, pending Grill decisions and evidence gaps. A clean result means only that no deviations were found in the stated coverage. Audit classifications are not `lean-review` verdicts, review receipts, gate passes or task completion evidence for unperformed checks.

Recommend bounded remediation groups and their acceptance checks. Do not edit application code, change the standards to hide findings, create a backlog or mark tasks DONE merely from the audit. If the user authorizes selected findings, route fixes through existing `lean-scope` / `lean-task`, tests, review and gate. Record resolved decisions/exceptions in the existing project records so later audits can reuse them. Audit output itself remains subject to the normal workflow's applicable completion requirements.

## Intensity

- **standard:** trace the selected baseline through a bounded area; report supported findings and coverage limits.
- **high:** follow relevant callers, dependencies and failure paths; cross-check evidence and proposed remediation dependencies.
- **ultra:** challenge consequential assumptions and cross-area invariants, seek contradictory evidence and identify migration/recovery risks within the selected scope. Depth never turns missing evidence into a pass or expands the audit automatically.

For behavioral evaluation of this skill, use [the scenario guide](references/scenarios.md); do not load or run it during ordinary audits. Actual agent trials complement packaging tests and do not prove universal runtime compliance.

$ARGUMENTS
