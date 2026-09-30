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

Review costs a full context each round, so the loop needs an end that is not the budget running out.

- A review cycle covers one Task Contract. A change stays in the cycle, and counts toward the round
  cap below, when its motivation is a finding from this cycle's review. Work that arrives mid-cycle
  for any other reason is new work: its own contract line, its own cycle, and its depth set by its
  own risk rather than inherited from this one. A contract opened because the cap fired says so, so
  the spend already made stays visible.
- After the second `REWORK` on one contract, the cycle gets one last pass. The delta it reviews must
  hold the fix for those findings, plus whatever repair validation demands of that fix, and nothing
  else. `PASS` there ends the cycle. `REWORK` there ends it as `BLOCKED`, naming what is unresolved
  -- never `DONE`: the delta that ships has to have been reviewed, not merely reviewed to the right
  depth. Going further is the user's call and their budget. This bounds how often a change is
  reviewed, never how deeply.
- A `PASS` ends the review. Anything applied afterwards is new work under the one-contract rule
  above, whatever its size: its own contract line, and no review when that contract is trivial.
  There is no carve-out for small fixes, because there is no cost to route around -- `WORKFLOW.md`
  already lets a trivial task skip formal review, so the whole price of a typo is one line. Every
  carve-out tried here leaked: the agent calling a change small is the one who wrote it, and the
  last independent look is already behind it.

## Independent reviewer

For `HIGH` depth, use a separate reviewer (for Claude, the `reviewer` subagent; otherwise a subagent or a fresh session) that sees the diff and Task Contract, not the worker's reasoning. If none is available, do a separate review pass against the Review Contract and state in the result that review was not independent.

## Reviewer rules

- Review the diff and its direct dependencies; do not rebuild full context.
- Report concrete findings: location, problem, severity, fix.
- No praise, no style nits unless they change meaning.
- Verdict is `PASS` or `REWORK`.
