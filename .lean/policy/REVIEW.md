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

- A review cycle covers one Task Contract. A change stays in the cycle, and counts toward the
  round cap below, when a finding from this cycle's review motivated it. Anything else arriving
  mid-cycle is new work: its own contract line, its own cycle, its depth from its own risk. A
  contract opened because the cap fired says so, so the spend stays visible.
- After the second `REWORK` on one contract, the cycle gets one last pass, over a delta holding the
  fix for those findings plus whatever repair validation demands of that fix, and nothing else.
  `PASS` there ends the cycle. `REWORK` there ends it as `BLOCKED`, naming what is unresolved —
  never `DONE`: the delta that ships has to have been reviewed, not merely reviewed to the right
  depth. Going further is the user's call and their budget. This bounds how often a change is
  reviewed, never how deeply.
- A `PASS` ends the review. Anything applied after it is new work under the one-contract rule
  above, whatever its size — its own contract line, no review when that contract is trivial, and no
  carve-out for small fixes. Inside a high-risk area `WORKFLOW.md`'s trivial test cannot be met at
  all, because every change there is `HIGH` risk, so even a typo costs a full cycle.

## Independent reviewer

For `HIGH` depth, use a separate reviewer (for Claude, the `reviewer` subagent; otherwise a subagent or a fresh session) that sees the diff and Task Contract, not the worker's reasoning. If none is available, do a separate review pass against the Review Contract and state in the result that review was not independent.

## Reviewer rules

- Review the diff and its direct dependencies; do not rebuild full context.
- Report concrete findings: location, problem, severity, fix.
- No praise, no style nits unless they change meaning.
- Verdict is `PASS` or `REWORK`.
