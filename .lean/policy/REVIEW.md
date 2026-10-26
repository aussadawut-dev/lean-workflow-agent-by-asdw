# Review

Deterministic validation runs first. Semantic review comes after and never replaces it.

## Depth by risk

- `LOW` — self-check against acceptance criteria.
- `MEDIUM` — focused review of the diff for correctness and regressions.
- `HIGH` — independent reviewer, edge cases, failure modes, security/data impact.

Depth follows risk, not model confidence. Quality also sets a minimum depth: `STANDARD` -> any, `HIGH` -> at least `MEDIUM`, `VERY_HIGH` -> `HIGH`. Use the deeper of the two: risk `LOW` with quality `VERY_HIGH` gets `HIGH` review.

## Rounds

- One cycle covers one Task Contract. Fixes motivated by its findings stay in that cycle; unrelated work needs a new contract and its own review depth.
- After the second `REWORK`, allow one final pass containing only those fixes and repairs required by their validation. `PASS` ends the cycle; another `REWORK` means `BLOCKED`, with unresolved findings. Further rounds require the user's decision and budget; a new contract must disclose the exhausted cycle.
- A `PASS` ends review. Any later applied change needs a new contract, including small fixes. Only work meeting `WORKFLOW.md`'s trivial criteria skips review; changes in a HIGH-risk area never qualify.

## Independent reviewer

For `HIGH` depth, use a separate reviewer (Claude's `reviewer` subagent; for Codex or agy, a subagent or a fresh session) that sees the diff and Task Contract, not the worker's reasoning. A Codex subagent must start fresh, never as a fork of the author's thread: with Codex's `spawn_agent`, set `fork_turns` to `"none"` and put `.lean/roles/reviewer.md`, the exact Task Contract and the diff range in its message. A forked reviewer inherits the author's reasoning and is not independent. Select its model and effort per `MODELS.md`; independence does not require a stronger model. If none is available, do a separate review pass against the Review Contract, state that it was not independent, and report `BLOCKED` until the required review can run.

Before reviewing, capture `python3 .lean/bin/lean evidence state`. The reviewer records its verdict with `python3 .lean/bin/lean evidence record-review --contract '<exact contract line>' --reviewer '<reviewer identity>' --state '<captured state>' --verdict PASS --evidence '<scope, round and findings>'`. Use `REWORK` for a failed review. Only the reviewer records the receipt: the author never records it, even with the reviewer's verdict in hand, and reports `BLOCKED` when the reviewer cannot record. The contract guard denies a main-thread `record-review` that names the session's own declared contract. The receipt binds the contract to the reviewed content (Git-visible paths with their bytes, modes and links, gate controls, and each submodule's full state) and to HEAD's tree when review began. Staging reviewed bytes keeps it valid, and so does a commit once HEAD holds the whole reviewed content. Any other content change, a staged blob or deletion that differs from the working tree, or a commit of only part of the change or of unreviewed bytes invalidates it. Tracker files directly under `docs/tracking/` are left out so the review result can be recorded after review (`lean mode check` validates them). Check it with `lean evidence check-review --contract '<exact contract line>'` before DONE. Untracked shipping files must be included in review.

This receipt detects stale coverage. Its identity and findings are attestations; it cannot prove reviewer independence against a writer with access to the same checkout.

## Reviewer rules

- Review the diff and its direct dependencies; do not rebuild full context.
- Check the diff against project standards routed from `.lean/PROJECT.md` for the touched areas. Block (`REWORK`) only on violations of mandatory rules that the diff introduces or modifies; pre-existing violations on unchanged lines are non-blocking notes.
- Report concrete findings: location, problem, severity, fix.
- No praise, no style nits unless they change meaning.
- Verdict is `PASS` or `REWORK`.
