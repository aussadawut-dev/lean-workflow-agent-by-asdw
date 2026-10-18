# Tracker and mode transitions

[Back to README](../README.md)

Run the CLI examples from the repository root.

A tracker is the workset you come back to in another session. It keeps the goal, acceptance criteria, decisions, progress and evidence together. Tracker and full modes require one for non-trivial work.

## Work with a tracker

Create one in tracker or full mode:

```sh
python3 .lean/scripts/workflow.py tracker new --id TCK001 --title "Implement sign-in"
```

Fill in the goal, acceptance criteria, decisions, task progress, evidence and next step. Update it after meaningful progress. Supported statuses are `PLANNED`, `IN_PROGRESS`, `VALIDATING`, `REVIEWING`, `DONE`, `BLOCKED` and `FAILED`.

Before setting `DONE`, the CLI requires evidence and checked acceptance/task lists. Full mode also requires all linked queue items to be DONE. Record completion after the actual Quality Gate and required review pass.

## Archive completed trackers

Archive `DONE` trackers to `docs/history/agent-workflow/` to keep `docs/tracking/` focused on active work and eliminate context waste:

```sh
python3 .lean/scripts/workflow.py tracker archive --dry-run
python3 .lean/scripts/workflow.py tracker archive --apply
# Or archive a specific tracker:
python3 .lean/scripts/workflow.py tracker archive --id TCK001 --apply
```

`python3 .lean/scripts/workflow.py context` prints mode, the active tracker and its next step, claims, Git state and the last gate result as JSON (the gate status comes from Claude Stop hook markers, so a direct runner or Codex run reads as `NOT_RUN` or `STALE`), to resume work after a break or context loss. `context` only reads, so it runs without a Task Contract; `tracker archive`, including `--dry-run`, counts as a write for the contract guard and needs one first (the first line of your reply in Claude, or `declare`).

## Upgrade or downgrade modes

Move to a higher mode with `configure`. Existing records stay in place:

```sh
python3 .lean/scripts/workflow.py configure tracker
python3 .lean/scripts/workflow.py configure full
```

To move to a lower mode, preview first and then apply explicitly. For full → tracker:

```sh
python3 .lean/scripts/workflow.py downgrade tracker --dry-run
python3 .lean/scripts/workflow.py downgrade tracker --apply --keep-pending
```

Supported routes are **full → tracker**, **tracker → standard**, and **full → standard**. `configure` refuses an implicit downgrade.

- Preview writes nothing. It reports counts, pending IDs, active/expired claims and blockers as JSON. Exit code 2 means blocked or refused, including invalid data or a missing acknowledgment.
- Active claims block every downgrade. Have the owning worker complete or release them. To move to standard, also resolve trackers in IN_PROGRESS, VALIDATING or REVIEWING.
- `--keep-pending` acknowledges that unfinished queue work will be kept and paused. For standard, it also acknowledges PLANNED/BLOCKED/FAILED trackers. It cannot bypass active-work or validation guards. Leave it out when nothing is pending.
- Apply takes the shared lock, checks the state again and updates config atomically. Records, IDs, evidence, expired lease files, execution settings and custom config fields stay intact.
- Lower modes stop requiring the disabled layer. Queue commands need full; tracker commands need tracker/full. Retained records are kept with their existing status.

Moving back up validates the retained records first. If a tracker became DONE while its queue was paused and still unfinished, reopen it in tracker mode before returning to full. Keep completion evidence truthful.

Without an existing lock, preview is a snapshot for planning; apply always locks and rechecks. Stop workers using older tooling before upgrading, and avoid manual edits to config or records while the command runs.
