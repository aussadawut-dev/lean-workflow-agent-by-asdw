# Queue validation, CI sharding and feedback measurements — 2026-10-24

Full-mode queue validation now indexes tracker documents once per `items()` call. The local synthetic 1,000-item cases improved substantially; smaller cases were noisy, including one regression. These measurements do not establish overall agent speed or token savings.

## Historical first optimization: measured bottleneck and change

A preliminary profile of full-mode `check` with 1,000 items and 1,000 distinct tracker documents took 1.526 seconds under profiling, including 1.406 seconds in `tracker_file`: 1,000 resolutions caused 2,000 calls to `tracker_matches`. Each queue item rescanned active and archived tracker directories.

The first candidate (hash `11331ae…` below) lazily builds an invocation-local count by exact tracker ID, scanning active `*.md` files and nested archived `*.md` files once. Queue validation then resolves each reference from that count. The index is rebuilt on the next invocation, so moves, deletion, additions and another root cannot reuse stale results. Empty queues and items failing basic validation do not build it.

Exact ID and hyphen suffix matching, file-only linkage, duplicate/missing errors, nested archive support and the exclusion of non-Markdown originals remain covered by tests. Standalone tracker mutation/archive resolution and symlink validation at `locked()` entry are unchanged. This targets full-mode queue linkage; other validation work remains.

## Reproduction and source identity

The original results below are historical and retain their original source hashes. Replay the first candidate from the retained patch; the current working source includes the later sparse refinement. Run from the repository root:

```sh
git show c5247c7067381fe7364c7794cfa44ba52546380a:.lean/scripts/workflow.py > /tmp/lean-workflow-baseline.py
cp /tmp/lean-workflow-baseline.py /tmp/lean-workflow-first-candidate.py
patch /tmp/lean-workflow-first-candidate.py < docs/benchmarks/2026-10-24/sparse-before.patch
python3 docs/benchmarks/2026-10-24/benchmark_queue.py \
  --baseline /tmp/lean-workflow-baseline.py \
  --candidate /tmp/lean-workflow-first-candidate.py \
  --output /tmp/lean-queue-timings.json --runs 5 --sizes 10 100 1000
```

Source SHA-256:

| Version | SHA-256 of `workflow.py` |
|---|---|
| Baseline | `d52914204a63a2a285b0407ae880060b4a11233095c58c4241eb4464536ae281` |
| Candidate | `11331ae4757b9a6fd52fb7ce4989911309b40774672c341e9ae5849eadc900ea` |

The [harness](benchmark_queue.py) creates disposable full-mode fixtures with N DONE queue items and N tracker files. In `shared`, every item references TCK001 and the other tracker files are unrelated archived documents. In `distinct`, every item references a different tracker, half active and half nested in history. Each version receives one warm-up per case, followed by five sequential pairs with alternating version order. Timings include CLI startup and exclude fixture setup. Successful output and unchanged fixture contents are checked. No model calls are involved.

The [raw report](queue-timings.json) retains every sample, source hashes, host information and load averages. Host: macOS 27.0.1 arm64, Python 3.14.3, 8 CPUs. The benchmark did not overlap this task's full test suite. Other host activity was uncontrolled; one-minute load averages ranged approximately 20–25, so small absolute differences require caution.

## Results

Medians in seconds; change is candidate time relative to baseline (negative means less elapsed time).

| Items / tracker files | Layout | Baseline | Candidate | Change |
|---|---|---:|---:|---:|
| 10 / 10 | shared | 0.142826 | 0.121466 | −15.0% |
| 10 / 10 | distinct | 0.207119 | 0.166696 | −19.5% |
| 100 / 100 | shared | 0.236087 | 0.323149 | +36.9% |
| 100 / 100 | distinct | 0.213226 | 0.156798 | −26.5% |
| 1,000 / 1,000 | shared | 1.690551 | 0.112367 | −93.4% |
| 1,000 / 1,000 | distinct | 1.240251 | 0.168004 | −86.5% |

The 1,000-item speed ratios are approximately 15.04× and 7.38× for these fixtures. The 100-item shared case regressed and is retained, without a selective rerun. Smaller-workload improvement is unproven: timings overlap substantially, and CLI startup and shared-host load are material. Five local samples and synthetic layouts do not predict every repository or filesystem. The deterministic regression test separately bounds tracker-directory enumeration to one scan per location per queue validation; wall-clock speed is not a test threshold.

## Sparse queue follow-up (step 1)

A same-source preflight measured Q=1 and Q=10 linked queue items against 10,000 tracker documents before selecting a change. The [preflight samples](sparse-preflight.json) use the first candidate for both labels: sparse shared medians were approximately 0.135–0.143 seconds and distinct medians 0.232–0.247 seconds. Even a single requested tracker caused every unrelated document to receive an `is_file()` check and a count entry. This justified filtering the existing scan rather than adding an adaptive per-ID rescan strategy.

The refinement lazily collects valid referenced IDs from already loaded active and archived queue sources after the first item's basic validation. It still enumerates active/history Markdown paths once, but only calls `is_file()` and stores counts for referenced IDs. There is no persistent cache; directory traversal and queue parsing still scale with record count. Standalone tracker operations and locked symlink checks are unchanged. A deterministic regression failed before the fix (102 document checks for two requested IDs), then passed with exactly two. Additional tests cover archived queue linkage/duplicates and first-source error precedence when a later tracker field is malformed.

The extended harness accepts independent `--cases ITEMS:TRACKERS`; its existing `--sizes` default invocation still runs equal-count fixtures. Every archived document and every unrelated active document has valid tracker content. Shared places only TCK001 active and the rest in nested history; distinct places odd IDs active and even IDs in nested history. Unlinked active documents use PLANNED, while linked documents use DONE. Unlinked archived documents in these new runs are PLANNED; linkage does not require an archived status. The historical harness used DONE for all documents, so retain the historical results as their own experiment. The empty case uses PLANNED trackers. No queue history volume is fabricated for timings because tracker-history cost is the variable under test; archived queue sources have separate correctness coverage.

Seven sequential alternating pairs per case, one warm-up per version, CLI startup included, fixture setup excluded. All checks returned the expected success output and left fixture contents unchanged. These benchmarks did not overlap test suites. Host/Python metadata and every sample are retained in [sparse-queue-timings.json](sparse-queue-timings.json). One-minute load averages ranged 4.93–5.54; other host activity was uncontrolled.

| Queue items / tracker files | Layout | Before | After | Change |
|---|---|---:|---:|---:|
| 0 / 10 | shared | 0.048863 | 0.048850 | -0.0% |
| 0 / 10 | distinct | 0.048367 | 0.048827 | +1.0% |
| 1 / 10 | shared | 0.049590 | 0.050361 | +1.6% |
| 1 / 10 | distinct | 0.050083 | 0.050158 | +0.1% |
| 1 / 10000 | shared | 0.137454 | 0.109248 | -20.5% |
| 1 / 10000 | distinct | 0.233334 | 0.216049 | -7.4% |
| 10 / 10000 | shared | 0.134279 | 0.109396 | -18.5% |
| 10 / 10000 | distinct | 0.237808 | 0.212088 | -10.8% |
| 1000 / 1000 | shared | 0.086697 | 0.085630 | -1.2% |
| 1000 / 1000 | distinct | 0.115139 | 0.116400 | +1.1% |

Sparse shared medians fell 18–21% and sparse distinct medians fell 7–11% in this local run. The deterministic stat/allocation reduction supports the change; elapsed-time estimates remain host-specific. Empty/small cases and dense guards changed by about 0–2% in absolute small amounts, so no speedup is claimed there. This does not establish full-suite, token, context or overall agent speed improvements.

Replay both snapshots from commit `c5247c7067381fe7364c7794cfa44ba52546380a`; the patches include the prior accepted index change as well as this refinement where applicable:

```sh
git show c5247c7067381fe7364c7794cfa44ba52546380a:.lean/scripts/workflow.py > /tmp/lean-sparse-before.py
cp /tmp/lean-sparse-before.py /tmp/lean-sparse-after.py
patch /tmp/lean-sparse-before.py < docs/benchmarks/2026-10-24/sparse-before.patch
patch /tmp/lean-sparse-after.py < docs/benchmarks/2026-10-24/sparse-after.patch
python3 docs/benchmarks/2026-10-24/benchmark_queue.py \
  --baseline /tmp/lean-sparse-before.py --candidate /tmp/lean-sparse-after.py \
  --output /tmp/lean-sparse-timings.json --runs 7 \
  --cases 0:10 1:10 1:10000 10:10000 1000:1000
```

Before SHA-256: `11331ae4757b9a6fd52fb7ce4989911309b40774672c341e9ae5849eadc900ea`. After SHA-256: `ed3690bf55e45e5220ffa611346c4afc4158be44c3b98d7e8ac403afe9f3b8fb`.

All three requested implementation steps are complete with local evidence: sparse queue refinement, CI sharding and completion-order feedback. Required Controller review and the final integrated Quality Gate are separate completion requirements; this report does not claim either has passed.

## Full-suite/CI sharding (step 2)

CI now runs `python3 .lean/tests/run_tests.py --shards 6`. The existing runner splits each Python file across up to six processes; its worker pool remains bounded by `os.cpu_count()`. All four Ubuntu/macOS × Python 3.9/3.13 matrix combinations and all other steps are unchanged. This experiment ran locally on macOS 27.0.1 arm64 / Python 3.14.3 with eight CPUs; remote CI and those Python versions were not executed. Six shards follow the existing project-gate setting; this is not a search for an optimal shard count.

The [measurement harness](benchmark_ci_sharding.py) ran two sequential pairs, alternating order 1→6 then 6→1, with `-j 8` in both arms. On this host that equals the CI command's default eight workers. No measured source changed and no other task-owned heavy test/benchmark ran concurrently. The runner scheduled 21 processes with one shard and 119 with six, with at most eight runner jobs active at once; subprocess work inside existing tests is unchanged. Timings include discovery, process startup, result capture and actual-ID recording. There was no warm-up, selective rerun or discarded sample.

| Pair | Order | One shard (seconds) | Six shards (seconds) | Elapsed change |
|---|---|---:|---:|---:|
| 1 | 1→6 | 191.700 | 105.655 | −44.9% |
| 2 | 6→1 | 159.796 | 89.037 | −44.3% |
| Median | | 175.748 | 97.346 | −44.6% |

All four runs passed all 21 Python files. The [raw report](ci-sharding-timings.json) retains every command, sample, pre/post load average, source fingerprint, discovered inventory and actual-ID list. Pre/post one-minute loads ranged 12.47–21.19, with an intermediate observation of 34.53 during the first baseline. Other host activity was uncontrolled. Consistent paired reductions support selecting six shards here; two local pairs do not establish an exact CI speedup or cross-platform result. Historical full-suite timings elsewhere in this report are not comparison arms.

A temporary `sitecustomize.py` wrapped `unittest.TestResult.startTest` in child interpreters and appended IDs to per-process logs. It recorded only tests whose class module's source file belongs directly to this checkout's `.lean/tests`; nested disposable fixture tests were excluded. The tiny self-check recorded two IDs exactly once and verified unrelated-source exclusion before timing. Both arms had identical instrumentation; its overhead was not measured separately and is absent from shipping CI. Final successful child results establish successful outcomes in addition to recorded starts.

At this frozen stage, discovery found **445 unique IDs**. Every run actually started precisely those 445 IDs once: no missing IDs, unexpected IDs or duplicates. Sorted inventory/actual SHA-256: `17e86d485824aab66ed6a20d2cb0bbd884d25164a137aa9b88ff1243bee6734a`. The completion-order regression adds one test afterward; this experiment remains a historical 445-test snapshot. The [source patch](ci-sharding-source.patch), against `c5247c7067381fe7364c7794cfa44ba52546380a`, freezes the measured `.lean/scripts/` and `.lean/tests/` changes, and the report identifies their exact hashes. In a disposable checkout at that commit, apply it with `patch -p1 < /path/to/ci-sharding-source.patch` before replaying.

The existing `test_run_tests.py` regressions passed within every full run, including exact-once sharding and failure reporting. Additional [disposable probes](verify_ci_sharding_failures.py) exercised default worker settings with both one and six shards: success returned zero, while a planted Python failure, a failed shard, shell-suite failure and import failure all returned one and retained their messages. All ten probes passed; [sanitized output and commands](ci-sharding-failures.json) are retained. The six-shard probe flags match CI, with only `--start-dir` selecting disposable fixtures. No failure semantics or test selection was weakened.

Replay from the repository root after restoring the measured source. Choose a fresh runtime directory: the harness refuses to overwrite existing per-run logs. Timing assertions check coverage/success/source identity, not a flaky elapsed-time threshold.

```sh
python3 docs/benchmarks/2026-10-24/benchmark_ci_sharding.py \
  --output /tmp/ci-sharding-replay.json \
  --runtime /tmp/lean-ci-sharding-fresh --jobs 8 --pairs 2
python3 docs/benchmarks/2026-10-24/verify_ci_sharding_failures.py \
  /tmp/ci-sharding-failures-replay.json
```

Step 2 changes CI configuration and documentation, using existing sharding behavior. Step 3 below changes the runner's reporting order. The project gate, permissions and workflow mode are unchanged. Required semantic review and the final integrated Quality Gate remain Controller work.

## Completion-order feedback (step 3)

The runner now submits jobs to the same bounded worker pool and consumes completed futures. It prints and flushes each completed job's status immediately. Every scheduled job still runs after failures; detailed failure blocks and the final failed-name recap retain submission order, exit status and content. This improves status feedback only: captured traceback details still print after all jobs finish.

A real-runner regression blocks the first job on an explicit release marker, then requires a later fast failure's status while that marker is absent and the runner is still alive. The original runner failed after the generous 10-second observation window; cleanup released the blocked child. With the change, all 14 focused runner tests passed, including this regression, passing jobs after failure, shard exact-once coverage, failed shards, shell errors, import errors and final recap checks. The timeout is a safety bound, not a speed threshold.

The [feedback harness](benchmark_feedback.py) runs five sequential alternating pairs with two workers: the first job creates a marker then sleeps 1.5 seconds, the second waits for that marker then fails, and a third passes. Setup is excluded, CLI startup included, and no warm-up or concurrent test suite was used. [Every sample and output event](feedback-timings.json) is retained with host metadata and source hashes. Medians in seconds:

| Observation | Before | After |
|---|---:|---:|
| First failure status | 1.622919 | 0.113015 |
| Entire synthetic run | 1.635739 | 1.620115 |

Failure-status latency fell about 93% in this deliberately blocked-first fixture. Total duration remained about 1.6 seconds; no whole-suite speedup is claimed for reporting order. Five synthetic pairs on a shared macOS host do not predict real failure latency, remote CI results, token use or agent performance.

Before runner SHA-256: `6f874a69f3afb1e121509f2273f15bbc85b133e7cafb5a0826bbb3020afc54e5`. After: `0bd05ba4386ed6a5ed04069d3a958ed1f9c7c5084bfe5163e4a7117b4d4ef1e1`. The [feedback patch](feedback-source.patch) freezes the runner and regression against `c5247c7067381fe7364c7794cfa44ba52546380a` (these two files were unchanged during steps 1–2). Replay the small benchmark independently:

```sh
git show c5247c7067381fe7364c7794cfa44ba52546380a:.lean/tests/run_tests.py > /tmp/lean-feedback-before.py
git show c5247c7067381fe7364c7794cfa44ba52546380a:.lean/tests/test_run_tests.py > /tmp/lean-feedback-tests.py
# In a disposable checkout at that commit, apply feedback-source.patch with patch -p1.
# Copy its updated runner to /tmp/lean-feedback-after.py, then run:
python3 docs/benchmarks/2026-10-24/benchmark_feedback.py \
  --baseline /tmp/lean-feedback-before.py --candidate /tmp/lean-feedback-after.py \
  --output /tmp/lean-feedback-replay.json --pairs 5
```

The single final integrated suite uses `python3 .lean/tests/run_tests.py --shards 6`. Its [recorder wrapper](record_final_feedback_suite.py) reuses the earlier recorder without running the two-arm benchmark. [The final report](feedback-final-suite.json) records current discovery and actual executed IDs independently, source hashes, elapsed time, exit status, missing/unexpected IDs and duplicates. It is separate from the historical 445-test experiment and from the Controller's Quality Gate and semantic review. Raw output and process ID logs stay under ignored `.agent-runtime/performance-20261024/feedback-final/`.

## Initial local observations

Before implementation, three runs per lightweight command produced these medians in the existing unconfigured standard/direct checkout:

| Command | Median seconds |
|---|---:|
| `python3 .lean/scripts/workflow.py --root . check` | 0.072338 |
| `bash .lean/scripts/check-structure.sh` | 0.170650 |
| `python3 .lean/scripts/model_catalog.py --root . check` | 0.050681 |

One baseline `python3 .lean/tests/run_tests.py` invocation passed all 21 Python test files in 164.007 seconds externally measured. Its slowest file, `test_gate_integrity.py`, took 163.9 seconds and set the critical path. Local samples and output are retained under ignored `.agent-runtime/performance-20261024/baseline.json` and `baseline-full-python-1.log`; these observations are not a controlled before/after whole-suite comparison. The queue optimization does not imply a speedup for standard mode or the full suite.

## Prioritized follow-up experiments

P1 and P2 have local implementation evidence above. P3 remains a proposed experiment:

1. **P1 — Full-suite and CI sharding (implemented locally).** CI now selects six shards with the CPU-sized pool. The paired macOS experiment above preserves actual test IDs and failure behavior; Linux and remote matrix timing remain unmeasured. This result is independent of the queue benchmark.
2. **P2 — Earlier test-runner feedback (implemented and measured).** Completed jobs now report immediately; a synchronized subprocess regression and the separate latency/duration experiment above retain evidence. Detailed failure blocks still wait for suite completion.
3. **P3 — Actual agent outcomes, tokens and context.** Use the existing [`evals/measure.py`](../../../evals/measure.py) extraction/report tooling with retained sanitized artifacts. Compare matched cases, providers/models/runtimes and revisions; record correctness, false success, elapsed time, tokens, tool turns and user exchanges, leaving unavailable values unknown. Include observed context reads when evaluating context selection. Real paid sessions require a separately approved explicit budget before execution. Current synthetic fixtures cannot establish token or context savings.

Defer gate caching and permission/policy changes until a specific measured bottleneck justifies their scope. Such changes require their own HIGH-risk contract and independent review. This report records implementation and measurement evidence; final integration review and the Quality Gate are separate completion requirements.
