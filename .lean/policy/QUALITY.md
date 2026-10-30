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

`lean gate run` executes the commands between PROJECT.md's gate markers and fails on missing or empty checks. Every provider uses this one runner: Claude's Stop hook (`lean hook claude stop`), Codex's trusted Stop hook (`lean hook codex stop`) and explicit runs (Codex without trusted hooks, agy, CI, people). Gate runs hold a per-checkout lock until their checks exit; busy or unavailable locks return NOT_RUN, never PASS. A direct run prints a bar per check.

Every continued Stop is checked. A refusal this session has already been shown, with the same reason, shipping state and contract, is released at once on a later Stop with a user-visible UNVERIFIED message. Another session, a new reason, or a Stop without a session id blocks as usual. Otherwise, after three continued refusals the Stop is released the same way so the agent can report BLOCKED; contract refusals always use this cap. A release never records a pass, cache or receipt, and the next Stop after a change is gated again. SessionStart records a change baseline, not validation. Checks rerun by default. `--cache-tree` opts into caching only for commands whose inputs are entirely Git-visible; a pass made with it, by a direct run or either provider's Stop, records the shipping state, and a later `--cache-tree` run or Stop on that unchanged state reuses it while contract, review-receipt and High-risk checks still run. A direct run's pass skips only the checks: it never makes changed work count as unchanged for the Claude Stop's transcript-contract check. Any refusal other than a contract refusal drops the record.

While an independent review runs, the Controller may mark it pending (`lean gate review-pending --contract '<exact contract line>' --session <id>`), which writes `.agent-runtime/review-pending.json` with the contract, session, captured shipping state (`lean evidence state`), time and a digest of the current receipt file. A Stop of that session (either provider) whose only refusal is the missing or stale review receipt for that contract is then released at once with a user-visible "review pending; UNVERIFIED; not DONE" message, and is not counted towards the cap; the marker itself acknowledges the gap, so its first Stop is not blocked again. Changed gate controls that only that review can accept are released the same way, with checks NOT_RUN, when the contract needs HIGH depth (`risk=HIGH` or `quality=VERY_HIGH`). A failing check, contract refusal, unreadable control records, drift under a lower-depth contract, another contract or session, or a direct `lean gate run` still blocks. A changed shipping state, a newly recorded receipt (PASS or REWORK) or a marker older than two hours ends the quiet period and removes the marker. A pending release, like every release, records no pass, cache or receipt.

Both providers' PreToolUse hooks run the shared contract guard (`lean hook <provider> pre-tool`): write tools and writing shell commands are denied until the session binds a Task Contract (in Claude, from the first text of the reply to the latest person prompt in the transcript; otherwise by `lean contract declare`), a person's prompt clears the declaration (in Claude, not one typed while the agent is still working), and a guard that cannot decide denies. It also denies a main-thread `lean evidence record-review` for the session's own declared contract, so only a reviewer subagent or a separate reviewer session records the receipt. Stops use the session's declared contract for changed work; a Codex Stop with changes since its session baseline and no declaration is refused. Codex applies hooks only after runtime hook trust; agy has none, so its agents declare and run the gate themselves. HIGH risk or VERY_HIGH quality also requires a matching PASS review receipt, as does any uncommitted, untracked or session-committed change under a backticked path in PROJECT.md's High-risk areas, whatever risk the contract declares. That High-risk floor is met by the latest PASS receipt when it covers exactly the current shipping state and was recorded for a HIGH-risk or VERY_HIGH-quality contract; a receipt under a lower contract does not count, a HIGH or VERY_HIGH contract still needs a receipt for itself, and any further change needs a new review. The guard also refuses edits and shell writes to the receipt file, and treats copies of the evidence module and `xargs` pipelines as receipt calls. These checks are heuristics: a deliberate writer with checkout access can still forge a receipt.

After independent HIGH review, check the receipt with `lean evidence check-review --contract '<exact contract line>'`, or run both with `lean gate run --require-review --contract '<exact contract line>'`. Hook activation/trust remains runtime-owned and must be verified separately; installing files alone does not prove activation.

Before an expensive final run, `lean gate preflight --contract '<exact contract line>'` (with `--session` and `--require-review` when needed) reads the current receipt readiness, including retained target High-risk floors, without running PROJECT checks or writing gate/cache/approval state. Use it after focused deterministic validation and semantic review. A ready receipt is not a gate pass: it does not accept changed controls, replace checks, or authorize publication. The final gate still validates and enforces evidence against the final shipping state; preflight never changes deterministic-before-review ordering in `gate run` or `target gate`.

## Change-scoped checks, batches and flaky failures

A PROJECT.md gate command may run through `python3 .lean/bin/lean gate scope [--only GLOB]... [--always GLOB]... -- <command>`. It skips that one check, exiting 0 with a `gate scope: skipped` line, only when every changed path of the repository it runs in (working tree, index, untracked files and every commit since the merge-base with the remote default branch, so a pushed but unmerged branch still counts; submodule content counts whatever its ignore settings) is a work record (`docs/tracking/*`, `.agents/queue/*` and the same under `.lean/targets/*/`) or matches `--only`, and none matches `--always`. No change, no repository, no remote default branch (`<remote>/HEAD`, `main` or `master`), a Git error or `LEAN_GATE_SCOPE=full` runs it. Scope only suites whose inputs are code: keep lint, mode, model and record checks unscoped, and add an application pointer (`--only targets/<name>`) only when the target gate covers that application. Scoping decides what the current change needs; it never reuses an earlier pass.

A batch of tasks (several TCKs worked together) runs each task's focused tests while it is worked, then one full gate for the batch, or one per published part, instead of one per task. That run must cover the final shipping state of every task it closes; an edit after it needs a new run, and in `manual` modes one authorization may name every task in the batch.

A failure suspected to be flaky (the change does not touch what the check covers) gets at most 2 unchanged reruns and counts as passed only when a rerun passes. If both fail, stop rerunning, treat the gate as failed, and record the failure output in the tracker that follows test health; a flaky failure that recurs later is recorded too.


Optional project-owned `.lean/gate.json` contains `{"auto": true|false}` with optional `"fixloop": true|false` (`auto`, `manual`, `auto_fixloop` or `manual_fixloop`) and controls every provider. Missing settings preserve `auto`; malformed, non-boolean or duplicate settings or a symlink report NOT_RUN. `lean gate mode` inspects without writing; `lean gate mode <mode>` saves only this preference.

With `auto` or `auto_fixloop`, Stops run shared checks automatically. With `manual` or `manual_fixloop`, automatic Stops skip validation and report NOT_RUN; always obtain applicable user authorization for a full run before starting it (reusing matching workset/batch approval or an explicit `/lean-gate` invocation). In `auto_fixloop` and `manual_fixloop`, once the full gate runs, if any check fails, auto-loop: fix all actionable code, test and lint failures and re-run the gate until it passes without asking again between rounds, stopping only for genuine requirement/design questions or missing environment tools. Until validation, acceptance and required review cover the shipping state, retain VALIDATING/BLOCKED rather than DONE. A released Stop is never a gate pass. `LEAN_GATE_FORCE=1` makes a manual Claude Stop run the checks; invalid policy still blocks.

## Protected controls

The gate records its controls on first use: `.claude/settings.json`, `.codex/hooks.json`, `.lean/gate.json`, `.lean/bin/lean`, every module in `.lean/lean/` (the guard, the gate and both provider adapters among them) and PROJECT.md's gate block. It refuses later changes until an already approved change is recorded with `lean gate accept-controls --reason '<user approval reference>'`. Approval is not granted by this command; inspect the full controls delta before recording it. A change that an independent HIGH-depth PASS review covers is accepted automatically: a receipt for the session's Task Contract under HIGH risk or VERY_HIGH quality, whose captured state includes the changed controls, and in which every changed control is visible to Git and starts the reviewed diff at its accepted value; a control change committed before the review began, even if edited again, or an ignored control is not accepted. Only a contract the session declared through the guard enables this; the runner reads it from the guard's store by session id, never from the command line.

A project may instead name already reviewed upstream controls in PROJECT.md with one line, `<!-- trusted-control-refs: refs/remotes/origin/main refs/remotes/origin/develop -->`. When every control equals the tree of one listed ref, the runner records the change as automatic with that ref and continues. Only remote-tracking `refs/remotes/*` names are accepted, never a local branch, tag, `HEAD` or commit id, and Git replace objects are ignored. The line is itself a control. Protect those remote branches outside the agent's write authority.

Contracts, regression-test ordering, risk labels, review identities and record evidence are not independently verified. Local hooks and hashes help catch mistakes; they are not a tamper-resistant security boundary. Projects needing external enforcement must require trusted CI and protected merge permissions, administered outside the agent's write authority.

**No evidence, no DONE.**
**No useful evidence, no extra tokens.**
