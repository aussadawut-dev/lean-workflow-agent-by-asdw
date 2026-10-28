# Workflow, modes, trackers and queue

[Back to README](../README.md)

## Phases

```
contract -> scope -> implement -> test -> validate -> review -> gate -> done
```

Each phase is a seventh of the progress bar; `--done N --total M` fills the current phase. The rules for each phase live in [.lean/policy/WORKFLOW.md](../.lean/policy/WORKFLOW.md); `/lean-task` walks them in order. The [workflow map](workflow-map.md) draws every branch as a flowchart.

```sh
python3 .lean/bin/lean progress set implement --done 2 --total 5 --task "add login"
# ███████░░░░░░░░░░░░░ 34% implement 2/5 — add login
```

## Modes

| Mode | Keeps | Commands |
|---|---|---|
| `standard` | Evidence in the conversation | — |
| `tracker` | One `docs/tracking/TCKNNN[-slug].md` per non-trivial workset | `lean tracker new --id TCK001 --title "..."`, `lean tracker status --id TCK001 --status DONE --evidence "..."` |
| `full` | Tracker plus `.agents/queue/items/QNNNN.json` with lease claims | `lean queue list`, `claim`, `claim-next`, `heartbeat`, `complete`, `release` |

A tracker cannot become DONE while any acceptance criterion or task checkbox is unchecked or its Evidence section is empty. In full mode, a DONE tracker also needs every linked queue item DONE.

Upgrades (`standard -> tracker -> full`) keep every record. Downgrades are explicit: `lean mode downgrade <mode> --dry-run`, then `--apply` (`--keep-pending` to pause unfinished work). Active claims block any downgrade; in-progress trackers block `standard`.

## Queue leases (full mode)

Claims last 30 minutes. A worker claims with a stable random request ID and retries with the same ID after a lost response; it gets the same token. Only the token holder heartbeats, completes or releases. Completion needs evidence and DONE dependencies. Dependencies and exclusive scopes decide what `claim-next` hands out; one agent holds one claim at a time.

## Archive and resume

`lean tracker archive --dry-run|--apply` moves DONE trackers to `docs/history/agent-workflow/`; their IDs stay reserved. `lean mode context` prints a read-only summary (mode, active tracker and its next step, claims, Git status, last gate result, progress) for resuming after a break or a new session.
