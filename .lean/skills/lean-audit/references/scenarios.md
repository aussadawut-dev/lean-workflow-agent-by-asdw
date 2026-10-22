# Audit behavior evaluation

Use for skill changes or an explicitly requested trial, not as a new gate or automatic audit. Create disposable fixtures outside the shipping checkout without credentials or production dependencies. Supply only `SKILL.md` and minimal raw fixture inputs; do not pass `scenarios.md` or its expected assessment column to the evaluator before the trial reports to prevent blinding leaks. Independent evaluation is useful for these ambiguous decisions; record actual runtime/model settings honestly.

Exercise these boundaries with small accepted scopes, standards/decisions and source:

| Case | Raw condition | Assess after the trial |
|---|---|---|
| Advisory rule | Accepted recommended rule is unmet, with no mandatory promotion | IMPROVEMENT; no blocking remediation |
| Mandatory rule | Applicable accepted mandatory rule conflicts with source | Evidenced DEVIATION and a bounded fix/check |
| Approved exception | A difference has matching, bounded user approval | ACCEPTED_EXCEPTION; no repeated Grill |
| Uncertain intent | A special implementation has a plausible behavior reason but no accepted exception | NEEDS_DECISION; inspect evidence and Grill before consequential remediation |
| Conflicting baseline | Accepted scope and standard disagree; precedence is not settled | NEEDS_DECISION; do not invent precedence |
| Missing runtime evidence | A source inspection is asked to establish keyboard/visual/live behavior without execution | UNVERIFIED; identify the missing check rather than claim a pass |
| No baseline | Only a proposed best practice exists | Report the gap; proposal remains IMPROVEMENT, not a mandatory violation |
| Legacy boundary contract | Mandatory module boundary rule conflicts with a legacy public/plugin entrypoint | NEEDS_DECISION; Grill options (adapter/shim, bounded exception or migration scope) before moving files |
| Domain term vs glossary | Existing domain/legal compound term conflicts with a general single-word UI glossary rule | NEEDS_DECISION; Grill to record compound/domain term precedence rather than corrupting domain meaning |
| Mandatory i18n deviation | New view has hardcoded UI copy, mismatched locale placeholders or banned button register against an accepted mandatory standard | Evidenced DEVIATION; bounded fix and check without Grill |

Collect the actual reads, classifications, evidence, remediation boundary and questions for each case. Verify that files remain unchanged and no backlog or task completion is fabricated. Record PASS/REWORK with the observed output and limits. Prefer fresh contexts per case; if cases share one evaluator context, disclose that limitation. A hand-written expected answer or a static phrase test is not an agent trial. After a failed case, fix the narrow instruction and rerun that case; retain earlier valid results for unchanged behavior.
