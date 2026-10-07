# Workflow

## Repository modes

Use `python3 .lean/scripts/workflow.py show` before non-trivial work. It reads `.lean/config.json`, including a missing-file fallback. Missing config and `configured: false` use `standard` behavior while `/lean-init` is pending. Mode is a repository setting, separate from the Task Contract's quality level and the execution modes below.

Model and effort selection follows `MODELS.md` in all three repository modes.
Use `configure <mode> --execution direct|delegated` to choose execution independently; omitted execution preserves the current setting. Unconfigured templates use `standard`/`direct` until onboarding. Existing approved tasks may continue under that fallback; `/lean-init` asks for mode selection before new application implementation when no choice has been recorded.
The Bash hooks and `fcntl` lease tool support macOS, Linux and WSL with Python 3. Native Windows execution is not supported; do not promise it from passing Unix tests.

| Mode | Required path for non-trivial work |
|---|---|
| `standard` | Task Contract, work, validation, review, Quality Gate. |
| `tracker` | Standard path plus one `docs/tracking/TCKNNN.md` or `TCKNNN-slug.md` for each workset. Record goal, acceptance criteria, task states, decisions, evidence, and next step. Create/update it before implementation and synchronize it after material progress. |
| `full` | Tracker path plus an executable `.agents/queue/items/QNNNN.json` for each independently claimable task. Claim its exact ID through `.lean/scripts/workflow.py queue claim --id QNNNN --agent NAME --request-id UUID` before editing its scope; heartbeat during long work, complete with validation evidence, or release when unfinished. Synchronize queue then tracker before reporting DONE. |

Use `python3 .lean/scripts/workflow.py configure <mode>` to select a mode. `standard -> tracker -> full` upgrades preserve prior records. Explicit downgrades use `downgrade <lower-mode> --dry-run`, then `--apply` when requested.
Preview is read-only and reports blockers (exit 2); apply rechecks under the shared lease lock.
All active claims block a downgrade. IN_PROGRESS/VALIDATING/REVIEWING trackers block standard.
Pending queue items, and PLANNED/BLOCKED/FAILED trackers being paused by standard, require explicit
`--keep-pending` acknowledgment. Keep every record and expired claim file; do not mark work DONE
or release someone else's lease to enable a transition. Execution and quality floors are unchanged.
Upgrade checks retained records before changing config. Reopen a DONE tracker in tracker mode if
its queue remains unfinished before returning to full. Stop workers on older tooling before an
upgrade; the lock coordinates CLI operations in one checkout, not manual edits or other checkouts. Trivial work needs no tracker or queue item; full-mode edits to an existing claimed item's scope still require its claim.

In `full`, generate a random request ID before each claim attempt and keep it until the claim receipt is known. Retry with the same agent, queue ID, and request ID if the response is lost; the tool returns the same token. A new request ID cannot take over an existing lease. Only the token holder may heartbeat, release, or complete the claim. A retried completion with the same evidence removes a lease left by an interrupted completion.

```
Task Contract -> Context -> Decide when needed -> Work -> Test -> Validate -> Review -> Quality Gate -> DONE
```

## Queue cleanup

Use `/lean-clean-queue old` for DONE items completed strictly over 30 days ago, or `/lean-clean-queue all`
for every DONE item. Only explicit cleanup requests authorize apply; cleanup never runs merely
because a task finishes or a mode changes. The CLI is `clean-queue old|all --dry-run|--apply`.
Preview is read-only; apply locks and rechecks data. READY/BLOCKED records and trackers remain.

Age uses timezone-aware `completed_at`, recorded in UTC by completion. Legacy undated DONE items
are reported/skipped by old and eligible for all; do not infer dates. Archive snapshots retain
original JSON bytes, checksum, IDs, evidence, custom fields and archive metadata without expiry.
Keep `.agents/queue/history/` in version control. Browse it with `queue history [--id QNNNN]`.
Archived DONE items still satisfy dependency and tracker checks; they cannot be claimed/listed as
active work. Do not reuse archived IDs. Active claims on DONE records and invalid data block
cleanup; valid live claims on retained READY items are preserved and do not block it.

Each snapshot is published before source deletion. A process interruption may leave identical
copies; history is authoritative and retry removes the leftover source. A changed duplicate is
an error. A failed batch may have archived earlier items: report partial progress and retry after
resolving the error, never delete files by hand to bypass it. Stop old-tooling workers before cleanup.

## Steps

1. **Task Contract** — one contract line before any change. See `CONTRACTS.md`. Trivial tasks write `Contract: trivial (<reason>)`.
2. **Context** — load the smallest sufficient context. See `CONTEXT.md`.
3. **Decide when needed** — use `/lean-grill` if a material choice remains open or the task crosses a high-risk boundary. Record accepted decisions in the tracker when that mode is enabled. Routine clear tasks do not need a Grill round.
4. **Work** — implement using the simplest valid path.
5. **Test** — add/run tests for behavior changes. See `TESTING.md`.
6. **Validate** — deterministic checks first (build, lint, typecheck, tests). Commands live in `.lean/PROJECT.md`.
7. **Review** — depth by risk, one contract per review cycle, bounded rounds. See `REVIEW.md`.
8. **Quality Gate** — verify evidence against the quality floor. See `QUALITY.md`.

## Trivial task

A task is trivial when all hold:

- Risk is `LOW`.
- No behavior change, or a change fully covered by an existing test that is run.
- One file, or a mechanical edit across a few files (rename, typo, formatting).
- The goal is unambiguous.

Trivial tasks use the one-word contract and skip formal review. They still need evidence before DONE, such as a passing check or a stated reason none applies.

## Execution modes

- `DIRECT` — default when configuration `execution` is `direct`.
- `DELEGATED` — Controller assigns bounded work to one worker when `execution` is `delegated`; follow `/lean-multi-agent`. Missing required delegation reports BLOCKED.
- `SEQUENCE` — only for real dependencies between steps.
- `PARALLEL` — only for genuinely independent work.

## States

`PLANNED -> IN_PROGRESS -> VALIDATING -> REVIEWING -> DONE`
Failure states: `BLOCKED`, `FAILED`. Both are supported by tracker tooling; queue item states remain `READY`, `BLOCKED`, `DONE`. See `RECOVERY.md`.

DONE is set only by the Quality Gate, never by the worker's own claim.
