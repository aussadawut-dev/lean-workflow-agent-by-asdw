# Queue and local ownership

[Back to README](../README.md)

Run the CLI examples from the repository root.

In full mode, queue items keep dependencies and ownership explicit. Create the owning [tracker](tracker.md) first. A lease is a temporary claim on a task, renewed while the worker is still using it.

## Claim work in full mode

Configure full mode, create a tracker, then create queue items from `.lean/templates/queue-item.json` under `.agents/queue/items/`. Each needs a unique `QNNNN` ID, a valid tracker ID, dependencies and exclusive scope labels.

```sh
python3 .lean/scripts/workflow.py configure full
python3 .lean/scripts/workflow.py queue list
python3 .lean/scripts/workflow.py queue claim --id Q0001 --agent worker-a --request-id RANDOM-UNIQUE-ID
```

Replace `RANDOM-UNIQUE-ID` with a fresh random identifier of at least eight characters, such as a UUID. Keep it until you receive the receipt. If the response is lost, retry with the same agent, item and request ID to recover the same token. `claim-next` selects an eligible item when no specific ID was assigned.

Use the returned token to renew or release the claim:

```sh
python3 .lean/scripts/workflow.py queue heartbeat --id Q0001 --token 'TOKEN-FROM-RECEIPT'
python3 .lean/scripts/workflow.py queue release --id Q0001 --token 'TOKEN-FROM-RECEIPT'
```

A lease lasts 30 minutes. Renew it during long work. After validation and required review, complete the item with `queue complete --id Q0001 --token 'TOKEN-FROM-RECEIPT' --evidence 'ACTUAL-VALIDATION-EVIDENCE'`, then synchronize the tracker.

Completion rechecks dependencies and requires nonblank evidence. The CLI can check that evidence exists; you still need to make sure it is true.

## Clean completed queue items

Enable the optional skill pack first. In Claude, use the commands below; in Codex, use `$lean-prune` with the same arguments:

```text
/lean-prune queue old
/lean-prune queue all
```

| Selection | What gets archived | What stays |
|---|---|---|
| `old` | DONE items completed strictly more than 30 days ago, using `completed_at`. | Recent DONE, undated DONE, and every READY/BLOCKED item. |
| `all` | Every DONE item, including undated legacy items. | Every READY/BLOCKED item. |

Cleanup archives queue items and keeps their full history. Trackers stay where they are. The skill previews the selection and applies the requested cleanup using that authorization. Add `--preview` to inspect it without applying.

If discovery is unavailable, read the [shared procedure](../.lean/skills/lean-prune/SKILL.md), or use the CLI:

```sh
python3 .lean/scripts/workflow.py clean-queue old --dry-run
python3 .lean/scripts/workflow.py clean-queue old --apply
python3 .lean/scripts/workflow.py clean-queue all --dry-run
python3 .lean/scripts/workflow.py clean-queue all --apply
python3 .lean/scripts/workflow.py queue history
python3 .lean/scripts/workflow.py queue history --id Q0001
```

New completions record UTC `completed_at`. `old` reports and skips legacy DONE items without it; `all` can archive them. Exactly 30 days old stays in the queue until it passes that threshold. File modification time is never used as a completion date.

History in `.agents/queue/history/` keeps original JSON bytes, custom fields, evidence, IDs, checksum, archive time and selection, without automatic expiry. Commit this history when saving cleanup in your project; it is project data and does not belong in the distributable template.

Dependencies and tracker checks can resolve archived DONE items. Active queue lists and claims exclude them. You can read history after lowering the mode. `queue history` lists IDs/titles; `--id Q0001` returns the full snapshot, with original JSON in `content`. A checksum detects mismatched content but cannot prove the evidence is authentic.

Preview writes nothing. Apply takes the shared lock and checks the data again. Malformed data or live claims on DONE records block cleanup. Valid live claims on retained READY items are preserved and do not block it.

Each snapshot is written and synced before its source is deleted. An interruption can leave an identical source copy that is already logically archived; retrying finishes the removal. Recovery works per item, so report partial progress if a batch stops. Keep archived IDs reserved, retain prerequisite history and stop workers using older tooling before cleanup. The command does not commit or push for you.

## What local ownership covers

The CLI checks IDs, states, dependency cycles, completion evidence and tracker/queue consistency where the mode requires it. Claim operations cover exact-item selection, eligible-item selection, heartbeat, release, completion and retry recovery.

It refuses overlapping exact scope labels, multiple live claims for one agent and unfinished dependencies at completion. Configure, downgrade and worker operations share a lock; workers check the mode again after acquiring it.

Scope labels match exactly. A directory label does not automatically cover every descendant file label. Coordination applies to **one checkout**, so separate machines and worktrees need their own coordination. Tokens are receipts, not a security boundary. An expired lease also cannot stop a worker process that is still running.
