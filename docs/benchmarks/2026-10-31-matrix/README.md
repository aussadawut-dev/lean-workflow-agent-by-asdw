# Four-level actual-token experiment

Status: study measured and independently graded; **optimization target NOT MET across all four difficulties**. 48 trial slots produced 47 completed deliverables and one retained timeout. Only Low demonstrated >=20% fewer tokens with full frozen-rubric coverage: the best explored profile averaged **43.65% less**, scoring 6/6 in both repeats, matching both controls. No shared Lean runtime or global policy has been changed.

## Results

Mean actual input+output tokens, two repeats per arm/task. Negative reduction means more tokens than 4.17.0. V1–V4 are exploratory interventions on the same bank; selecting a best observed arm is not held-out confirmation.

| Task | 4.17.0 | 5.8.0 | V1 prose | V2 packet | V3 protocol | V4 late evidence |
|---|---:|---:|---:|---:|---:|---:|
| Low | 280,926.5 | 282,176 | 371,683 | 181,161.5 | **158,296.5** | 178,914.5 |
| Medium | **210,014.5** | 325,703 | 272,344.5 | 234,558.5 | 231,790.5 | 248,268 |
| High | **216,118.5** | 289,304.5 | 299,055.5 | 316,828 | 334,075.5 | 346,683.5 |
| Critical | 524,299 | N/A: timeout + 667,995 | 552,801.5 | 611,839.5 | **518,669.5** | 579,767 |

| Profile | Low reduction | Medium reduction | High reduction | Critical reduction | Equal-weight reduction | Full target |
|---|---:|---:|---:|---:|---:|---|
| V1 prose | -32.31% | -29.68% | -38.38% | -5.44% | -26.45% | FAIL |
| V2 packet | 35.51% | -11.69% | -46.60% | -16.70% | -9.87% | FAIL |
| V3 protocol | **43.65%** | -10.37% | -54.58% | 1.07% | -5.06% | FAIL |
| V4 late evidence | 36.31% | -18.21% | -60.41% | -10.58% | -13.22% | FAIL |

Even the best single profile increased the equal-weight token cost versus 4.17.0. The >=20% overall/per-level goal remains unmet; this report does not describe an achieved global optimization.

## Independent quality outcome

A fresh auditor requested as `gpt-6.1-sol/high` received randomized answer IDs, the frozen criteria and pinned source, with **no arm names, token counters or parent history**. It graded all 48 answers; [grades.json](grades.json) binds the findings to answer hashes. Values below are the two coverage scores, not a production-security verdict.

| Arm | Low /6 | Medium /6 | High /8 | Critical /8 |
|---|---|---|---|---|
| 4.17.0 | 6, 6 | 5, 5 | 8, 8 | 5, 5 |
| 5.8.0 | 6, 6 | 5, 6 | 8, 8 | 0 (timeout), 4 |
| V1 prose | 5, 6 | 6, 5 | 8, 8 | 5, 6 |
| V2 packet | 6, 6 | 5, 5 | 8, 8 | 5, 5 |
| V3 protocol | 6, 6 | 5, 5 | 8, 8 | 4, 4 |
| V4 late evidence | 6, 6 | 5, 6 | 8, 8 | 5, 6 |

Low V2/V3/V4 pass the no-quality-loss condition and the cost threshold; V3 has the lowest measured mean. High retains full coverage but costs more. Medium has missing hard-criterion details and some profiles fall below the better control's mean. Critical has missing required coverage in every arm, including the legacy baseline; it cannot be treated as a passing critical-safety analysis.

Audited omissions include local cleanup versus provider-side revocation, exact cleanup fixture bounds, merge/split validation/error cases, and the explicit permission-override regression. These are answer-coverage findings, not newly demonstrated application exploits. The auditor recorded no separate unsupported-factual-claim finding. Do not weaken the frozen criteria or shorten critical checks to make the token goal pass.

The separate auditor consumed 1,370,826 input tokens (1,235,584 cached) and 14,122 output tokens (3,444 reasoning). These subsets are not added twice. This is experiment overhead, excluded from per-investigator comparisons; the Controller's development/history tokens are not measured here.

## What to change next

The observed Low saving supports a bounded, opt-in investigation recipe. The broader goal requires a different mechanism than the four prompt/retrieval treatments tested here. The proposed next experiment is [atomic startup, exact cited reads and bounded worker contexts](NEXT-PROTOTYPE.md), measuring **Controller + workers + review + retries** together. That mechanism is a proposal, not a measured >=20% solution. It requires a separately accepted HIGH-risk implementation scope before touching the guard/entrypoint/canonical routing.

Keep the current safety, validation and review requirements. Do not make any tested profile a universal default or infer that rolling back runtime safeguards is justified by the legacy token advantage.

This extends [TCK028's single-task pair](../2026-10-31/README.md) with four distinct Casetodian source investigations, repeated controls and an explicit no-quality-loss condition. The user's reference is Lean **4.17.0**, not 4.17.1 or 5.5.0.

## Frozen acceptance

Primary cost = actual `input_tokens + output_tokens` from completed runtime usage. Cached input and reasoning output are subsets, never added twice. Target = at least 20% fewer tokens versus 4.17.0 in **each difficulty** and in the equal-weight mean of per-difficulty reductions. Also compare with unmodified 5.8.0, but saving against a regressed newer control alone does not meet the target.

Quality uses [frozen criteria](tasks.json) written before inference, based on the pinned application source. All optimized answers must complete, pass every hard criterion, have no supported finding of an unsupported factual claim, and reach at least the better control's mean rubric score at that difficulty. A shorter incomplete answer cannot pass. These are source-analysis quality criteria, not implementation, full-gate or production-security proof.

| Difficulty | Task | Requested model/effort, fixed across arms |
|---|---|---|
| Low | Navigation pins HTTP contract, schema, caller identity and test evidence | gpt-6.1-sol / medium |
| Medium | Gmail connector removal, cleanup and ordinary SMTP preservation | gpt-6.1-sol / medium |
| High | SMTP outbound SSRF, DNS, address classes and TCP/TLS destination | gpt-6.1-sol / high |
| Critical | Identity tenant/permission boundaries, retirement, split/merge interleavings and privacy evidence | gpt-6.1-sol / high |

## Experiment and intervention history

The original frozen matrix is 4 tasks x 3 arms x 2 repeats = 24 trial slots. Arms are 4.17.0, 5.8.0 and 5.8.0 plus [focused prose v1](focused-context.md). Each task's second repeat reverses its first arm order; starting positions also rotate across tasks. Trials run sequentially under subscription auth. Source, task wording and within-task model/effort remain fixed. Fresh conversations do not imply cold provider caches.

V1 did not meet the target in the first repeat: Low, Medium and High consumed more than 4.17.0; Critical saved less than 20%. These failures remain in the data. Traces showed that a generic instruction to follow dependencies could broaden a small HTTP-contract question into an audit of shared auth/entitlement infrastructure.

V2 uses [question-bounded context guidance](focused-context-v2.md) plus [deterministic source retrieval](source_packet.py). Known paths, filename companions and named imports are collected into complete, line-numbered original files. This tool receives the question and application source, **not the rubric or expected answers**. Depth, omitted files and unresolved imports are explicit. Investigators still have full source for missing material dependencies. No model-generated summary substitutes for source evidence; safety/quality/gate requirements are not relaxed.

V2 adds 8 fresh trials (two per difficulty) after the frozen matrix. V3 adds 8 trials using [an actionable protocol](focused-protocol.md), and V4 adds 8 using [late/selective evidence](focused-late.md), for 48 slots in total. Existing controls are reused rather than silently rerun; original V1 failures are preserved. V2–V4 are exploratory and were developed after seeing earlier traces. Their trials are not interleaved with controls, so order/cache effects and tuning on this task bank limit generalization. Two repeats do not establish statistical noninferiority. Further unseen tasks and implementation/gate workloads would be necessary for a broad workflow-saving claim.

## Failure and usage rules

Each investigator has the same 300-second wall limit and an advisory 20-tool-call budget. Tool counts include failed/no-match commands. Exceeding advisory calls is reported; it does not erase cost. A timeout is a failed deliverable and is retained. If the CLI does not emit final usage, its partial cost is **unknown**, never zero or a free task. A reduction percentage is unavailable if either arm lacks complete usage for a required repeat. No failed trial is silently replaced with a successful retry.

The first Critical/5.8.0 trial timed out at 300 seconds after 19 completed commands; no `turn.completed.usage` was emitted. The next schedule slot was resumed without rerunning/replacing that trial. The analysis keeps its quality failure and does not fabricate its token count.

No quota saving will be inferred from token counts. Subscription quota snapshots are coarse, account-shared observations. [Official usage documentation](https://learn.chatgpt.com/docs/pricing) explains that context, caching, reasoning and tool use all affect usage. Investigator totals also exclude this Controller's development work and the separate quality auditor; those are experiment overhead, not hidden per-task savings.

## Evidence and tools

- [tasks.json](tasks.json): frozen questions, expected facts, hard criteria and requested model settings.
- [run_matrix.py](run_matrix.py): resumable, input-hashed first matrix; `--run` launches inference.
- [run_packet.py](run_packet.py), [run_protocol.py](run_protocol.py), [run_late.py](run_late.py): additional interventions, preserving every prior result.
- [quality_audit.py](quality_audit.py): independently grades randomized answer IDs without workflow-arm/token data; its usage is separate overhead.
- [analyze.py](analyze.py): rejects missing trials/grades, stale answer hashes, changed tasks/models, double-counted cache, incomplete cost comparisons and quality regressions.
- [test_matrix.py](test_matrix.py): offline checks; never launches inference.

Original application source pin: `d2ef08cf1a84aaaf5db527ea44a62a1c811c7701`. Fixtures export only Git-tracked source into disposable directories. The real Casetodian checkout, installed Lean controls, global policies and release refs are unchanged. This deliverable is a reusable optional investigation profile and evidence-retrieval tool, not a published Lean upgrade.

The source packet is a heuristic aid. It excludes dependency/build artifacts and refuses out-of-root entry paths/symlinks; it does not claim a complete TypeScript dependency graph. A regression test demonstrates that known entry paths must take priority over companion discovery to preserve import traversal.

Raw CLI JSONL/stderr and pre-launch dispatch records remain ignored under `.agent-runtime/token-matrix/`. Reports retain aggregate runtime counters, source/profile/task hashes and normalized returned messages; the timed-out trial has only a partial message and is explicitly marked incomplete. CLI requested model settings are recorded separately from any backend metadata; no unreported model substitution is assumed.


## Validation and artifacts

All 48 answer hashes, per-task question/model settings, usage subset bounds and source/profile identities are checked by the analyzer. Each [summary JSON](summary-protocol.json) records `target_met: false`; all four candidates retain their own `summary-*.json`. `matrix.json` plus `matrix-packet.json`, `matrix-protocol.json` and `matrix-late.json` retain raw observations and failed slots. Usage sums in an interrupted row with `usage_events: 0` are unavailable counters, not a zero-price run.

Offline harness: 13 tests PASS, including rejection of missing trials/grades, false savings from a timeout, unsupported claims, double-counted cache and hidden source-packet omissions. Lint PASS. Command scan inspected 590 completed investigator commands and found no pnpm/node/network/database execution commands; fixture/source Git checks remained clean. No application tests ran, as explicitly scoped.

The original 24-slot matrix observed the shared weekly quota at 61% before and 63% after. This includes account/Controller activity and is coarse; no per-arm quota percentage or conversion is established. Later profiles and grading have separately retained token counters, not attributed subscription percentages.

Publication formatting removed extra EOF blank lines from the timed-out partial message only. Its pre-publication/reviewed SHA256 is retained alongside the normalized-file SHA256 in matrix.json/grades.json. The auditor packet/hash and raw trace are unchanged; no answer fact, grade or completion status was changed.
