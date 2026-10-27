# Workflow

## Phases and progress

```
contract -> scope -> implement -> test -> validate -> review -> gate -> done
```

1. **contract** — one contract line before any change. See `CONTRACTS.md`. Trivial tasks write `Contract: trivial (<reason>)`.
2. **scope** — load the smallest sufficient context (`CONTEXT.md`); for non-trivial work agree the scope (`/lean-scope`) and use `/lean-grill` when a material choice remains open or the task crosses a high-risk boundary. Routine clear tasks do not need a Grill round.
3. **implement** — the simplest valid path.
4. **test** — add/run tests for behavior changes; run only what the change can affect (`TESTING.md`).
5. **validate** — deterministic checks first (build, lint, typecheck, tests). Commands live in `.lean/PROJECT.md`.
6. **review** — depth by risk, one contract per review cycle, bounded rounds. See `REVIEW.md`.
7. **gate** — verify evidence against the quality floor. See `QUALITY.md`.

On entering a phase, run `python3 .lean/bin/lean progress set <phase>` (add `--done N --total M` for countable work inside it, and `--task '<title>'` once per task) and show the bar it prints in the reply, for example `███████░░░░░░░░░░░░░ 34% implement 2/5 — add login`. Each phase is one seventh of the bar; counts fill the phase. `lean progress set done` marks the end. Trivial tasks may skip progress.

Every surface reads the same state file (`.agent-runtime/progress.json`): the agent's reply, `lean status`, `lean test`, `lean gate run`, `lean spawn run` (one bar per agent), Claude's status line, Codex's Stop message, and `lean watch` in a second terminal pane. Codex and agy have no custom in-window status line; they use the reply, the Stop message (Codex) and `lean watch`. Progress is display only, never evidence.

Every phase change, gate run, test run, spawned agent, contract binding and review receipt is also appended with its time to `.agent-runtime/activity.jsonl`. `lean log` prints the timeline, `lean log --summary` the time spent per phase and counts of gate runs, tests, agents and reviews, and `lean log --export docs/history/<name>.md` keeps a copy in the repository to review and improve the workflow later. The log is local and ignored until exported; it is never evidence for DONE.

## Repository modes

Use `python3 .lean/bin/lean mode show` before non-trivial work. It reads `.lean/config.json`, including a missing-file fallback. Missing config and `configured: false` use `standard` behavior while `/lean-init` is pending. Mode is a repository setting, separate from the Task Contract's quality level and the execution modes below.
Use `lean mode configure <mode> --execution direct|delegated` to choose execution independently; omitted execution preserves the current setting. The lease tool and hooks support macOS, Linux and WSL with Python 3; native Windows is not supported.

| Mode | Required path for non-trivial work |
|---|---|
| `standard` | Task Contract, work, validation, review, Quality Gate. |
| `tracker` | Standard path plus one `docs/tracking/TCKNNN.md` or `TCKNNN-slug.md` for each workset (`lean tracker new`). Record goal, acceptance criteria, task states, decisions, evidence, and next step. Create/update it before implementation and synchronize it after material progress. |
| `full` | Tracker path plus an executable `.agents/queue/items/QNNNN.json` for each independently claimable task. Claim its exact ID through `lean queue claim --id QNNNN --agent NAME --request-id UUID` before editing its scope; heartbeat during long work, complete with validation evidence, or release when unfinished. Synchronize queue then tracker before reporting DONE. |

`standard -> tracker -> full` upgrades preserve prior records. Explicit downgrades use `lean mode downgrade <lower-mode> --dry-run`, then `--apply` when requested. Preview is read-only and reports blockers (exit 2); apply rechecks under the shared lease lock. All active claims block a downgrade. IN_PROGRESS/VALIDATING/REVIEWING trackers block standard. Pending queue items, and PLANNED/BLOCKED/FAILED trackers being paused by standard, require explicit `--keep-pending` acknowledgment. Keep every record and expired claim file; do not mark work DONE or release someone else's lease to enable a transition. Upgrade checks retained records before changing config. Trivial work needs no tracker or queue item; full-mode edits to an existing claimed item's scope still require its claim.

In `full`, generate a random request ID before each claim attempt and keep it until the claim receipt is known. Retry with the same agent, queue ID, and request ID if the response is lost; the tool returns the same token. A new request ID cannot take over an existing lease. Only the token holder may heartbeat, release, or complete the claim. A retried completion with the same evidence removes a lease left by an interrupted completion. Queue history archived by 4.x (`.agents/queue/history/`) stays readable and keeps satisfying dependencies.

`lean tracker archive [--id TCKNNN] --dry-run|--apply` moves DONE trackers from `docs/tracking/` to `docs/history/agent-workflow/` only on an explicit request. It validates all records first and refuses invalid ones rather than hiding them from `check`. Archived trackers are read-only: they still satisfy queue links and their IDs stay reserved. `lean mode context` prints a read-only summary (mode, active tracker, claims, Git, last gate marker and progress) for resuming work.

## Trivial task

A task is trivial when all hold:

- Risk is `LOW`.
- No behavior change, or a change fully covered by an existing test that is run.
- One file, or a mechanical edit across a few files (rename, typo, formatting).
- The goal is unambiguous.

Trivial tasks use the one-word contract and skip formal review. They still need evidence before DONE, such as a passing check or a stated reason none applies.

## Execution

- `direct` — the active agent works; it spawns only when `MODELS.md` says spawning is cheaper or required.
- `delegated` — the Controller assigns bounded work to one worker; follow `/lean-agents`. Missing required delegation reports BLOCKED.
- Parallel agents only for genuinely independent tasks with exclusive file ownership, at the level the user chose (`MODELS.md`).

## States

`PLANNED -> IN_PROGRESS -> VALIDATING -> REVIEWING -> DONE`
Failure states: `BLOCKED`, `FAILED`. Both are supported by tracker tooling; queue item states remain `READY`, `BLOCKED`, `DONE`. See `RECOVERY.md`.

DONE is set only by the Quality Gate, never by the worker's own claim.
