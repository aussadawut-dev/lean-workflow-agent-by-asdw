# Tracker and mode transitions

[Back to README](../README.md)

Run CLI examples from the repository root.

Trackers retain acceptance criteria, decisions, status and evidence across sessions. They are required for non-trivial work in tracker and full modes.

## Work with a tracker

In tracker or full mode:

```sh
python3 .lean/scripts/workflow.py tracker new --id TCK001 --title "Implement sign-in"
```

Update the generated workset with the goal, acceptance criteria, decisions, task progress, evidence and next step. Synchronize it after material progress. Supported statuses are `PLANNED`, `IN_PROGRESS`, `VALIDATING`, `REVIEWING`, `DONE`, `BLOCKED` and `FAILED`.

The CLI requires evidence and checked acceptance/task lists before setting `DONE`. In full mode, all linked queue items must also be DONE. Only record completion after the actual Quality Gate and required review pass.

## Upgrade or downgrade modes

Upgrades use `configure` and preserve records:

```sh
python3 .lean/scripts/workflow.py configure tracker
python3 .lean/scripts/workflow.py configure full
```

To lower a mode, preview first, then apply explicitly. For example, from full to tracker:

```sh
python3 .lean/scripts/workflow.py downgrade tracker --dry-run
python3 .lean/scripts/workflow.py downgrade tracker --apply --keep-pending
```

Supported routes are **full → tracker**, **tracker → standard**, and **full → standard**. `configure` continues to refuse implicit downgrades.

- Preview writes nothing and reports counts, pending IDs, active/expired claims and blockers as JSON. Exit code 2 means blocked or refused, including invalid data or a missing acknowledgment.
- Active claims block every downgrade. Complete or release them through the owning worker. Moving to standard also requires resolving trackers in IN_PROGRESS, VALIDATING or REVIEWING.
- `--keep-pending` explicitly acknowledges preserved, paused queue work and, for standard, PLANNED/BLOCKED/FAILED trackers. It cannot bypass active-work or validation guards. Omit it when there is no pending work.
- Apply takes the shared lock, rechecks current state and atomically updates config. Tracker/queue records, IDs, evidence, expired lease files, execution settings and custom config fields stay intact.
- Lower modes stop requiring the disabled layer. Queue commands require full; tracker commands require tracker/full. Retained records are not deleted or automatically marked DONE.

Upgrading back validates retained records before enabling the higher mode. If a tracker was marked DONE while its queue was paused and remains unfinished, reopen the tracker in tracker mode before returning to full. Do not invent completion evidence to pass a transition.

Without an existing lock, preview is an advisory snapshot; apply always locks and rechecks. Stop workers using older tooling before upgrading, and avoid concurrent manual edits to config/records.
