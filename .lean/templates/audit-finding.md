# Audit report and finding format

Adapt to existing project records or report in the conversation. Copy only when saving is authorized. An audit does not create tasks or approvals automatically.

## Report context

- Requested area and exclusions.
- Accepted baseline: scope, standard IDs/versions and exception references.
- Inspected state: revision and relevant uncommitted changes.
- Coverage: inspected paths/flows, sampling, performed checks and unrun checks with reasons.
- Summary: findings by priority, accepted exceptions, open decisions and evidence gaps.

## Finding

- ID / title: stable report identifier.
- Classification: CONFORMS | DEVIATION | ACCEPTED_EXCEPTION | NEEDS_DECISION | UNVERIFIED | IMPROVEMENT.
- Requirement: applicable accepted rule or acceptance criterion and version; identify absent/conflicting baseline.
- Location: source paths/lines, flow or component.
- Evidence: observed behavior, code/test/runtime references; separate inference.
- Impact / priority: consequence and urgency with a reason.
- Confidence / uncertainty: what is supported and what remains unknown.
- Proposed action: preserve, remediate, investigate or propose a standard; identify dependencies.
- Grill decision: evidence, options, consequential differences and pending/accepted decision reference when needed.
- Verification: observable check for the proposed resolution.
- Exception: approval reference and applicable limits, if any.

Only evidenced conflicts with accepted requirements are DEVIATION. A new recommendation is IMPROVEMENT; unavailable verification is UNVERIFIED. A report of no deviations is limited to stated coverage and does not replace review or a gate.

Unmet recommended rules are nonblocking IMPROVEMENT unless an accepted scope/decision explicitly makes the rule mandatory. Cite that promotion when applicable; importance alone does not change strength.
