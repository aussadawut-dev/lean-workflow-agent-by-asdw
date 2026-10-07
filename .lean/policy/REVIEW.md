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

- One cycle covers one Task Contract. Fixes motivated by its findings stay in that cycle; unrelated work needs a new contract and its own review depth.
- After the second `REWORK`, allow one final pass containing only those fixes and repairs required by their validation. `PASS` ends the cycle; another `REWORK` means `BLOCKED`, with unresolved findings. Further rounds require the user's decision and budget; a new contract must disclose the exhausted cycle.
- A `PASS` ends review. Any later applied change needs a new contract, including small fixes. Only work meeting `WORKFLOW.md`'s trivial criteria skips review; changes in a HIGH-risk area never qualify.

## Independent reviewer

For `HIGH` depth, use a separate reviewer (Claude's `reviewer` subagent; for Codex, a subagent or a fresh session) that sees the diff and Task Contract, not the worker's reasoning. Select its model and effort per `MODELS.md`; independence does not require a stronger model. If none is available, do a separate review pass against the Review Contract, state that it was not independent, and report `BLOCKED` until the required review can run.

Before reviewing, capture `python3 .lean/scripts/gate_evidence.py state`. The reviewer records its verdict with `python3 .lean/scripts/gate_evidence.py record-review --contract '<exact contract line>' --reviewer '<reviewer identity>' --state '<captured state>' --verdict PASS --evidence '<scope, round and findings>'`. Use `REWORK` for a failed review. The receipt binds the contract to HEAD, index, Git-visible file contents/modes, links, gate controls and submodule state. Check it with `check-review --contract '<exact contract line>'` before DONE. Untracked shipping files must be included in review. Ignored application inputs still require the project's own checks.

This receipt detects stale coverage. Its identity and findings are attestations; it cannot prove reviewer independence against a writer with access to the same checkout.

## Reviewer rules

- Review the diff and its direct dependencies; do not rebuild full context.
- Report concrete findings: location, problem, severity, fix.
- No praise, no style nits unless they change meaning.
- Verdict is `PASS` or `REWORK`.
