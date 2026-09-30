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

- A review cycle covers one Task Contract. A change stays in the cycle, and counts toward the cap,
  when its motivation is a finding from this cycle's review. Anything else is new work: its own
  contract line, its own cycle. A contract opened because the cap fired says so, so the spend
  already made stays visible.
- After the second `REWORK` on one contract, the cycle gets one last pass, over the delta that fixes
  those findings and nothing else. `PASS` there ends the cycle. `REWORK` there ends it as `BLOCKED`,
  naming what is unresolved -- never `DONE`, because a delta no reviewer has seen cannot satisfy
  condition 4 in `QUALITY.md`. Going further is the user's call and their budget. This bounds how
  often a change is reviewed, never how deeply.
- A `PASS` ends the review. Afterwards you may apply a non-blocking finding only if the change is
  trivial by the test in `WORKFLOW.md` -- no behaviour change, or one an existing test already
  covers and you run. Anything larger is new work under the first rule: its own contract, its own
  review. The agent calling it cheap is the one who wrote the code, and the last independent look
  is already behind it.

## Independent reviewer

For `HIGH` depth, use a separate reviewer (for Claude, the `reviewer` subagent; otherwise a subagent or a fresh session) that sees the diff and Task Contract, not the worker's reasoning. If none is available, do a separate review pass against the Review Contract and state in the result that review was not independent.

## Reviewer rules

- Review the diff and its direct dependencies; do not rebuild full context.
- Report concrete findings: location, problem, severity, fix.
- No praise, no style nits unless they change meaning.
- Verdict is `PASS` or `REWORK`.
