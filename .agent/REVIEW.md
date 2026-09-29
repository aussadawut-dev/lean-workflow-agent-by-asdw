# Review

Deterministic validation runs first. Semantic review comes after and never replaces it.

## Depth by risk

- `LOW` — self-check against acceptance criteria.
- `MEDIUM` — focused review of the diff for correctness and regressions.
- `HIGH` — independent reviewer, edge cases, failure modes, security/data impact.

Depth follows risk, not model confidence.

## Resolving risk and quality

Quality also sets a minimum depth: `STANDARD` -> any, `HIGH` -> at least `MEDIUM`, `VERY_HIGH` -> `HIGH`.

Use the deeper of the two. Example: risk `LOW` with quality `VERY_HIGH` gets `HIGH` review.

## Independent reviewer

For `HIGH` depth, use a separate reviewer (a subagent, or a fresh session) that sees the diff and Task Contract, not the worker's reasoning. If none is available, do a separate review pass against the Review Contract and state in the result that review was not independent.

## Reviewer rules

- Review the diff and its direct dependencies; do not rebuild full context.
- Report concrete findings: location, problem, severity, fix.
- No praise, no style nits unless they change meaning.
- Verdict is `PASS` or `REWORK`.
