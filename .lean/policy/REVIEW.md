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

## Rounds

Review costs a full context each round, so the loop needs an end.

- A `PASS` ends the review. Apply the non-blocking findings that are cheap and clearly right, but
  do not open another round to check them. The next review, if the work earns one, covers them.
- After the second `REWORK` on one contract, stop and report what is left rather than starting a
  third round. The user decides whether to keep going; it is their budget. This caps the spend, not
  the depth.
- A review cycle covers one Task Contract. Work that arrives mid-cycle gets its own contract and
  its own review, even in the same files. Bolting it on restarts the rounds already paid for and
  hides which change a finding belongs to.

## Independent reviewer

For `HIGH` depth, use a separate reviewer (for Claude, the `reviewer` subagent; otherwise a subagent or a fresh session) that sees the diff and Task Contract, not the worker's reasoning. If none is available, do a separate review pass against the Review Contract and state in the result that review was not independent.

## Reviewer rules

- Review the diff and its direct dependencies; do not rebuild full context.
- Report concrete findings: location, problem, severity, fix.
- No praise, no style nits unless they change meaning.
- Verdict is `PASS` or `REWORK`.
