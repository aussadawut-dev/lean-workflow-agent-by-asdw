# Quality

## Quality floor

| Level | Meaning |
|---|---|
| `STANDARD` | Correct, tested where behavior changes, validated. |
| `HIGH` | STANDARD plus risk review and edge-case coverage. |
| `VERY_HIGH` | HIGH plus independent review and explicit failure-mode analysis. |

## Budget

`CHEAP | BALANCED | EXPENSIVE` controls effort and cost, never the floor. If the floor cannot be met within budget, report it; do not silently downgrade.

## Quality Gate

DONE requires all of:

1. Task Contract acceptance checks satisfied with evidence.
2. Deterministic validation passed (or not-applicable stated).
3. Tests present for behavior changes.
4. Review completed at the required depth (deeper of risk and quality; see `REVIEW.md`), covering the delta that ships.
5. No unreported skipped checks.
6. In `tracker` mode, the workset tracker is synchronized with the evidence and final status. In `full` mode, queue items have completion evidence, no active claim remains for completed work, and the owning tracker agrees with the queue.

## What is enforced

The shared runner executes PROJECT commands and fails on missing/empty checks. Every continued Claude Stop is checked. After three continued refusals the Stop is released with a user-visible UNVERIFIED message so the agent can report BLOCKED; a release never records a pass, cache or receipt, and the next Stop is gated again. SessionStart records a change baseline, not validation. Checks rerun by default. `--cache-tree` opts into caching only for commands whose inputs are entirely Git-visible; environment, installed dependencies and ignored files are outside that cache.

With a readable Claude transcript, changed work needs a first-line assistant contract in the current human turn, before recognized write tools. Runtime-injected skill bodies, hook feedback, task notifications and compaction summaries do not start a turn. HIGH risk or VERY_HIGH quality also requires a matching PASS review receipt, as does any uncommitted, untracked or session-committed change under a backticked path in PROJECT.md's High-risk areas, whatever risk the contract declares. An unreadable supplied transcript blocks; absent transcript metadata cannot enforce the contract. Shell writes and truthful risk/evidence remain procedural responsibilities.

Codex runs validation explicitly. After independent HIGH review, check the receipt with `python3 .lean/scripts/gate_evidence.py check-review --contract '<exact contract line>'`. `bash .lean/scripts/quality-gate.sh --require-review --contract '<exact contract line>'` combines validation and receipt checking when both need to run. No native Codex hook is claimed.

The runner records local gate controls on first use and refuses later hook/settings/gate-block changes until an already approved change is recorded with `python3 .lean/scripts/gate_evidence.py accept-controls --reason '<user approval reference>'`. Approval is not granted by this command. The baseline trusts first use and remains writable by the agent.

Contracts, regression-test ordering, risk labels, review identities and record evidence are not independently verified. Local hooks and hashes help catch mistakes; they are not a tamper-resistant security boundary. Projects needing external enforcement must require trusted CI and protected merge permissions, administered outside the agent's write authority. A workflow self-test does not prove application correctness or release readiness.

**No evidence, no DONE.**
**No useful evidence, no extra tokens.**
