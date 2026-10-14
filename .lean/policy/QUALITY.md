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

The shared runner executes PROJECT commands and fails on missing/empty checks. Gate runs hold a per-checkout lock until their checks exit. Busy or unavailable locks return NOT_RUN, never PASS; this does not serialize independent validation commands or freeze source edits. Every continued Claude Stop is checked. After three continued refusals the Stop is released with a user-visible UNVERIFIED message so the agent can report BLOCKED; a release never records a pass, cache or receipt, and the next Stop is gated again. SessionStart records a change baseline, not validation. Checks rerun by default. `--cache-tree` opts into caching only for commands whose inputs are entirely Git-visible; environment, installed dependencies and ignored files are outside that cache.

With a readable Claude transcript, changed work needs a first-line assistant contract in the current human turn, before recognized write tools. Runtime-injected skill bodies, hook feedback, task notifications and compaction summaries do not start a turn. HIGH risk or VERY_HIGH quality also requires a matching PASS review receipt, as does any uncommitted, untracked or session-committed change under a backticked path in PROJECT.md's High-risk areas, whatever risk the contract declares. An unreadable supplied transcript blocks; absent transcript metadata cannot enforce the contract. Shell writes and truthful risk/evidence remain procedural responsibilities.

Codex runs validation explicitly, or through the optional trusted `.codex/hooks.json` lifecycle adapter. After independent HIGH review, check the receipt with `python3 .lean/scripts/gate_evidence.py check-review --contract '<exact contract line>'`. `bash .lean/scripts/quality-gate.sh --require-review --contract '<exact contract line>'` combines validation and receipt checking when both need to run. Hook activation/trust remains runtime-owned and must be verified separately; installing files alone does not prove activation.

## Gate automation policy

Optional workspace-owned `.codex/quality-gate.json` contains `{"auto": true|false}` and controls both providers, including a selected target's checks. Missing settings preserve auto; malformed/non-boolean/duplicate settings or symlink boundaries report NOT_RUN. `python3 .lean/scripts/gate_mode.py` inspects without writing; explicit `auto` or `manual` saves only this preference. Preferences never ship as portable assets or override target acceptance and review requirements.

With auto=true, Claude Stop and an activated Codex Stop adapter run shared checks. With auto=false, automatic Stops skip validation and report NOT_RUN. Run focused checks normally; obtain applicable user authorization for a full run at work completion, reusing already matching workset/batch approval. Until validation, acceptance and required review cover the shipping state, retain VALIDATING/BLOCKED rather than DONE. A released Stop is never a gate pass.

Direct shared runner calls always execute regardless of mode. `python3 .codex/hooks/quality_gate.py run` also runs explicitly; `CLAUDE_GATE_FORCE=1 .claude/hooks/quality-gate.sh` forces the Claude adapter. Invalid policy still blocks provider adapters even when forced. SessionStart reads policy without validating; Claude seeding still records only a baseline. Codex automatic Stops reuse a PASS receipt only after verifying its contract and current shipping fingerprint, and require the runner to recheck it. Stale/missing receipts never bypass HIGH review. Automatic checks have no native current-turn Task Contract provenance: use the exact `--contract` and `--require-review` for explicit HIGH validation; a hook message does not establish acceptance for a new task.

Mode configuration, its shared helper and both provider adapters are protected gate controls. The existing accept-controls procedure records matching prior user approval, not permission granted by a toggle. Inspect the full controls delta before recording it; do not approve unrelated changes. Shared locking, cache opt-in and continued-refusal semantics remain in force. Codex asks to continue once on a failed fresh Stop, then releases continued Stops as UNVERIFIED without a pass; future fresh Stops run again.

The runner records local gate controls on first use and refuses later hook/settings/gate-block changes until an already approved change is recorded with `python3 .lean/scripts/gate_evidence.py accept-controls --reason '<user approval reference>'`. Approval is not granted by this command. The baseline trusts first use and remains writable by the agent.

Contracts, regression-test ordering, risk labels, review identities and record evidence are not independently verified. Local hooks and hashes help catch mistakes; they are not a tamper-resistant security boundary. Projects needing external enforcement must require trusted CI and protected merge permissions, administered outside the agent's write authority. A workflow self-test does not prove application correctness or release readiness.

**No evidence, no DONE.**
**No useful evidence, no extra tokens.**
