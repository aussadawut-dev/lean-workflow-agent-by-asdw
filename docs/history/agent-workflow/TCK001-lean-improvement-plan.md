# TCK001 — Lean improvement plan from the Astra review

Status: DONE
Owner: unassigned

## Goal

Make Lean easier and cheaper to complete work with while preserving observable acceptance, meaningful validation, independent review where required, and recovery of user work.

This tracker records the recommendations requested by the user after the conversation review. It is a proposal for future implementation, not a record of completed remediation.

## Scope and baseline

- Reviewed repository: `lean-workflow-agent-by-asdw`.
- Reviewed revision: `cfe8f82`, baseline 4.4.0 with Unreleased changes.
- Evidence method: reading documentation, scripts, hooks, skills and test source. No tests, behavioral eval sessions or Quality Gate were run for the review.
- Current authorization: create this planning record in a new worktree. Implementation decisions and behavior changes remain proposed.
- Preserve canonical shared instructions, provider parity, truthful validation status, bounded review rounds, recovery safeguards and existing project choices.
- Prefer improving existing procedures over adding skills or configuration axes. Avoid unrelated cleanup or a broad workflow rewrite.

## Acceptance criteria

- [x] AC-01: A documented finalization protocol allows a reviewed HIGH-depth change to complete queue/tracker updates and the intended Git staging/commit sequence without unexplained receipt invalidation. Changes to reviewed behavior, relevant instructions or validation controls still invalidate evidence appropriately.
- [x] AC-02: The approved contract/scope lifecycle reuses valid user authorization and context during a continuing task, while material scope changes and unresolved material decisions still stop dependent work. Both providers have equivalent intended outcomes and documented runtime gaps.
- [x] AC-03: Behavioral evals cover the approved finalization lifecycle, continuing conversations and independent functional outcomes. Review cases check valid final review evidence, rather than only reviewer dispatch.
- [x] AC-04: Cost and outcome comparisons can be reproduced from a committed script and retained sanitized artifacts, reporting task correctness, total usage/cost where available, elapsed time and user interventions with model/runtime/revision/run-count details. Template changes and project-local settings are reported separately.
- [x] AC-05: Current documentation agrees with implemented tracker archival and Codex contract enforcement; other documentation edits stay within the affected routes.
- [x] AC-06: Each implemented work item has its required deterministic validation and semantic review over the state that ships. Missing or deferred checks remain explicitly unverified.

## Tasks

- [x] TASK-05 / Priority 1: Reconcile affected documentation with current behavior (AC-05, AC-06).
- [x] TASK-01 / Priority 2: Resolve review evidence and finalization ordering (AC-01, AC-06).
- [x] TASK-02 / Priority 3: Reduce the remaining contract and scope interruptions (AC-02, AC-06).
- [x] TASK-03 / Priority 4: Extend behavioral evals to completion and functional outcomes (AC-03, AC-06).
- [x] TASK-04 / Priority 5: Make cost measurement reproducible (AC-04).

## Findings and proposed approach

### TASK-01 — Review evidence and finalization

Evidence: [`lean-task`](../../../.lean/skills/lean-task/SKILL.md) orders semantic review (step 6) before completion/evidence and tracker synchronization (step 7). [`gate_evidence.py`](../../../.lean/scripts/gate_evidence.py) `state()` hashes `git rev-parse HEAD`, the gate controls, the raw `git ls-files --stage` output and the bytes/modes/links of every Git-visible path, including untracked ones; `check_review()` compares that digest with the receipt. `docs/tracking/` is not ignored, so tracker edits are part of the state. [`test_gate_integrity.py`](../../../.lean/tests/test_gate_integrity.py) (`test_high_review_is_required_and_bound_to_current_bytes_modes_and_index`) asserts that `git add` alone invalidates a PASS receipt, so this binding is intended behavior today.

Static conclusion: bookkeeping edits after review, staging, or committing change the receipt state even when reviewed source bytes are unchanged. A commit changes HEAD; staging changes the index blob ids; a tracker update changes Git-visible bytes.

Reproduced on 2026-10-17 at `246c83f` in a disposable fixture with copies of the gate scripts, comparing `gate_evidence.py state` (the value `check-review` compares) after an untracked reviewed change: setting the tracker to DONE changed the state (reverting it restored the state); `git add` of the reviewed file changed it; committing the staged state changed it although the tree did not change. Each step alone invalidates a PASS receipt. The comparison used `state` directly because the contract guard correctly denies a main-thread `record-review`.

Recommended approach (to confirm with a reproduction before implementation):

1. Bind the receipt to content identity rather than Git bookkeeping: the set of Git-visible paths with their bytes, modes and links, the gate controls and submodule state. Drop the HEAD commit id and the raw index listing, so staging and committing the reviewed bytes keep the receipt valid. Dropping only HEAD is insufficient, because staging changes the index blob ids. Cover staged versus unstaged deletions, renames and mode changes with tests.
2. Move tracker synchronization that does not depend on the review verdict to before review, so the reviewer sees it.
3. Decide the remaining post-review edit (recording the verdict and DONE status in the tracker) as an explicit TASK-01 decision: either a narrowly specified tracker-evidence exemption or a cheap re-check after that edit. Do not broadly ignore Markdown, configuration or all tracker changes.

Prefer this over a staged/two-phase finalization protocol, which adds procedure for a problem the state identity causes. [`REVIEW.md`](../../../.lean/policy/REVIEW.md) already states that the receipt detects stale coverage and does not prove reviewer independence, so removing HEAD and index bookkeeping from it does not weaken an existing guarantee. Keep independent validation of records and relevant Git state, and preserve independent reviewer ownership of review receipts.

Planned validation: a meaningful lifecycle case covering HIGH change → deterministic validation → independent PASS → queue completion → tracker synchronization → intended staging/commit → final gate. Include negative cases where a source, instruction or control change must invalidate prior evidence. Update the staging assertion in `test_gate_integrity.py` deliberately, as an approved behavior change. Confirm review-round limits and receipt ownership remain intact.

### TASK-02 — Contract and scope lifecycle

Evidence: [`lean-scope`](../../../.lean/skills/lean-scope/SKILL.md) requires approval of a newly drafted spec and says an implementation request alone does not approve it. [`contract_guard.py`](../../../.lean/scripts/contract_guard.py) clears declarations on human prompts. Existing accepted scope can already be reused; preserve that behavior.

Already addressed in the Unreleased 4.4.0 work ([changelog](../../../.lean/CHANGELOG.md)): Claude's PreToolUse guard binds the contract from the first reply line through the transcript, and plain `grep`, `cat`, `head`, `tail`, `wc`, `ls` and read-only `git` subcommands run before a contract. Do not redo that work.

Remaining concerns:

- The pre-contract shell allowlist still excludes common inspection commands such as `rg`, `sed -n` and `find`, and any command joined with `;` or `&&`.
- The transcript binding can miss a contract line written in the same reply. In the review session, tool calls made after a reply that opened with the contract line were still denied, and the agent spent an extra turn on `contract_guard.py declare`. This happened in two separate prompts.
- A clear implementation request may still incur an additional approval exchange, and a status question or correction during the same task can force declaration work again.

Proposed approach: define when an explicit user request already supplies sufficient accepted scope, when a continuing task retains its contract, and which changes require a new contract or approval. Expand read-only handling only where command intent can be identified reliably. Compare reducing guard parsing complexity with extending its heuristics; do not assume the local guard is a security boundary. Investigate the missed same-reply binding before widening any allowlist.

Planned validation: clear request; existing accepted scope; status-only follow-up; bounded correction; material expansion; conflicting requirements; resumed session; runtime notification; both providers. Measure avoided interruptions and verify that material decisions still block dependent work. This changes workflow authority and needs accepted scope before implementation.

### TASK-03 — Behavioral eval coverage

Evidence: [`cases.py`](../../../evals/cases.py) defines six behavior cases. The `high-review` graders check contract, reviewer dispatch (`reviewer_dispatched`), suite result and change claims; they do not assert that `.agent-runtime/review.json` holds a PASS receipt covering the final state. An agent that dispatches a reviewer and then keeps editing passes the case. The fixtures exercise small applications, with limited coverage of tracker/full closeout or continuing conversations.

Proposed approach: add independent functional assertions for requested behavior, verify final receipt coverage and independence, and cover tracker/full finalization, follow-up messages and resume. Preserve useful existing regression-order and truthful-claim graders. Distinguish tooling unit tests, agent procedure compliance and user-visible task outcomes.

Planned validation: each added grader has positive and negative fixtures, including an agent that follows the visible steps but produces a wrong outcome or stale receipt. Check Codex fresh-review detection against explicit `fork_turns: "none"` and omitted/default values. Paid behavioral runs require their own applicable authorization and budget.

### TASK-04 — Cost and outcome measurement

Evidence: the [Unreleased changelog](../../../.lean/CHANGELOG.md) reports first-turn usage of 29,859 → 28,513 tokens for template text changes (about 4.5%). The 27% comparison also includes project-local tool/skill visibility settings. Its 16-run smoke comparisons are reported historical evidence, not measurements reproduced by this review. The maintainer already measures each release this way; what is missing is a way for others to reproduce the numbers.

Proposed approach: commit the measurement procedure as a script, using the existing eval harness where possible, and retain enough sanitized artifacts to reproduce published claims. Report correct completion, false success, blocked outcomes, total tokens, monetary cost where available, wall time, tool turns and required user exchanges, with template-only changes separated from local settings.

Out of scope: a new multi-arm paid study comparing the current workflow, a proposed revision and a lightweight baseline. Its likely result (the lighter baseline costs less) does not justify the spend; reconsider only if TASK-01 to TASK-03 change costs materially. Keep paid calls opt-in; do not infer authorization from this tracker.

### TASK-05 — Documentation consistency

Evidence: [`CUSTOMIZING.md`](../../../.lean/CUSTOMIZING.md) says "Tracker archival is not implemented", while [`workflow.py`](../../../.lean/scripts/workflow.py) implements `tracker archive` and the [tracker guide](../../tracker.md) documents it. [`evals/README.md`](../../../evals/README.md) says Codex's Stop hook does not check the contract line, while the [Codex adapter](../../../.codex/hooks/quality_gate.py) refuses changed work that has no declared contract for the session.

Proposed approach: correct these two statements and inspect directly affected references. Preserve historical changelog entries as history. Prefer behavioral evidence over tests that merely pin exact prose; retain structural checks where they protect an actual discovery or authority boundary.

This task runs first: it is small, low risk and independent of every other task.

Planned validation: compare current claims with their implementation and relevant existing tests. Documentation-only edits should not introduce new policy or expand the maintenance task.

## Decisions

- The user requested saving the review recommendations in a new worktree and accepted a TCK document as the format.
- The recommended sequence is TASK-05 → TASK-01 → TASK-02 → TASK-03 → TASK-04. TASK-05 goes first because it is independent and low risk. Correct other directly affected documentation alongside each implementation.
- TASK-01 uses content-identity receipts rather than a two-phase finalization protocol. The user approved the TASK-01 scope and chose option 1: top-level `docs/tracking/*.md` records are left out of the receipt state and stay validated by `workflow.py check`.
- TASK-04 is limited to reproducible measurement; a new multi-arm paid study is out of scope.
- No remediation approach, workflow authority change, paid experiment, mode change or publication is approved merely by recording this plan.
- Existing `standard` / unconfigured / `direct` settings are retained. This explicitly requested planning record does not enable tracker or full mode.
- Risk and quality are determined separately for each implementation contract. Hook, policy and permission/authority changes must follow the applicable higher review requirements.

## Evidence

- Conversation: review of the local repository followed by the request to record the recommendations in a new worktree, optionally as a TCK.
- Follow-up review of this plan checked each cited file and line against revision `cfe8f82`: every finding matched the code. That review reordered the tasks, narrowed TASK-02 and TASK-04, and added the TASK-01 recommendation.
- The findings above are static observations or explicitly labeled inferences. Existing test source was read; its existence does not establish that tests currently pass.
- TASK-01 review round 1: REWORK. The reviewer found that a commit of unreviewed bytes, a staged deletion of a file still on disk and a partial commit kept the receipt valid, and that blob ids were abbreviated. Fixed by recording HEAD's tree in the receipt and checking the index and HEAD against the reviewed content (`shipping_gap`); four regression tests failed before the fix and pass after.
- TASK-01 review round 2: REWORK. A commit between the reviewer's state capture and recording could ship unreviewed bytes, and `core.fileMode=false` hid staged or committed mode changes. Final bounded pass: the captured `state` binds HEAD's tree, and gap checks force `core.fileMode=true`; two regression tests failed before and pass after.
- TASK-01 final review pass: PASS, recorded by the independent reviewer; `check-review` passes. Accepted known gaps: intermediate commits with unreviewed bytes stay in history when the final tree matches the reviewed content, and forcing `core.fileMode=true` can refuse a valid receipt on filesystems without modes.
- TASK-01 done in `7939a6d`: the user accepted the protected control change, the full Quality Gate passed with the review receipt check, and `check-review` still passed after the commit. Implementation: `gate_evidence.py` adds `review_state()` (CLI `state`) for receipts and keeps `state()` (new CLI `gate-state`) for the gate cache and baselines; `quality-gate.sh` uses `gate-state`; `REVIEW.md`, `lean-task` and the changelog describe the new binding and order. New tests failed before the change (3 of 5; the 2 regression guards already passed) and pass after: all 360 `.lean/tests` (after the round-2 fixes), 108 hook tests, eval harness tests and every PROJECT gate command run directly.
- TASK-02 scope approved by the user (items A–C; changing `lean-scope` approval of implementation requests stays out). Root cause of the missed binding, from replaying this session's transcript: `transcript_contract()` found the first-line contract in every denied turn, and the text was written 1–37s before the denied tool call, so Claude had not yet saved the reply when PreToolUse ran (an inference; waiting longer in the hook would not help). Implemented, pending independent review and user acceptance of the protected control change: (A) the guard's denial and `AGENTS.md` say to `declare` first when a turn's first tool call writes; (B) `read_only_shell` adds `rg`, `sort`, `cut`, `find`, numeric-range `sed -n … p` and `&&`/`;` chains, each with write-capable forms refused; (C) `quality-gate.sh` releases a repeated gate refusal for the same shipping state and contract at once (contract refusals keep the three-refusal cap; `--seed` clears it). `CONTRACTS.md`, `QUALITY.md` and the changelog match. New tests failed before and pass after; the hook tests that expected three identical refusals were updated as an intended behavior change.
- TASK-02 review round 1: REWORK. Findings: the Stop fingerprint ignored the refusal reason, so a failing check after accepted drift was released unseen; shlex treated `a#` as a comment and hid chained commands; bfs `find -rm`, `rg --hostname-bin` and abbreviated `sort --out=` could write or run programs; the fingerprint was shared by concurrent sessions. Fixed: the fingerprint includes the session id and a checksum of the run's messages (no session id means no release), `#` stays inside words, and `rg`, `sort` and `find` use allowlists. Regression tests failed before and pass after.
- TASK-02 review round 2: PASS, recorded by the independent reviewer. Accepted low findings: check output that varies between runs (timings, temp paths) never matches the fingerprint, so such a repeated failure keeps the three-refusal cap (errs toward blocking); the saved stderr descriptor is inherited by check commands, harmlessly.
- TASK-02 done: the user approved the protected `quality-gate.sh` change on 2026-10-18 and ran `accept-controls` themselves (the auto-mode classifier refused it from the agent); the full Quality Gate passed with the round-2 PASS receipt; the full `.lean/tests` suite (20 files), 107 hook tests and shellcheck passed before the gate.
- TASK-03 and TASK-04 dispatched in standard mode: `Dispatch TASK-03 | role=worker | requested model/effort=sonnet/medium | reason=normal implementation | reported model/effort=unavailable/unavailable`, and TASK-04 with the same settings. The worker worktrees branched from `main`, so the Controller integrates their diffs here.
- TASK-03 done: `review_receipt_final_state` (independent PASS that `check-review` accepts for the final state, no main-thread `record-review`) on `high-review` and the new cases; `outcome(...)` functional graders; new `tracker-finalization`, `followup-new-contract` and `followup-after-review` cases with `tracker_done`, `work_committed`, `final_gate_after_last_change`, `contract_each_writing_turn` and `no_writes_in_last_turn`; `Conversation` follow-ups sent as resumed turns; Codex reviewers fresh only with explicit `fork_turns` none/0. Each new grader has positive and negative fixtures. Gaps: resuming a later session is not covered; resumed-turn CLI paths are unit-tested with a fake runner only, because paid runs were not authorized.
- TASK-04 done: `evals/measure.py` `extract`/`report` with sanitized `lean-measure/1` artifacts in `evals/measurements/` (moved from the git-ignored `evals/results/`), a labeled synthetic sample and 12 tests. The changelog's historical 4.4.0 numbers cannot be reproduced: their raw runs were not retained.
- Integrated validation after TASK-03/04: `check-structure.sh` ok, `.lean/tests` 20 files OK, eval tests 58 OK (46 harness + 12 measure), `tools` tests OK, `run_evals.py --dry-run` builds all 9 fixtures. Paid evals: NOT_RUN.
- TASK-03/04 review round 1: PASS, recorded by the independent reviewer subagent under this session's contract; `check-review` passes. Accepted LOW findings: a hand-written receipt with a plausible reviewer name and the correct state, written without the receipt command, would pass `review_receipt_final_state` (`reviewer_dispatched` partly covers it); the `false_success` claim regex is heuristic; the resumed-turn command shapes are unverified against live runtimes.
- TASK-05 done; `.lean/CUSTOMIZING.md` now points to `workflow.py tracker archive`, and `evals/README.md` describes Codex's PreToolUse and Stop contract enforcement. `git grep` found no other current statement of either claim. TASK-03 and TASK-04 not started.
- Paid evals: NOT_RUN.

## Next step

None. All TCK001 tasks are done. Optional follow-ups: a paid eval run to confirm the resumed-turn paths and the Codex `fork_turns` default, and committed measurement artifacts behind the next release's cost claim.
