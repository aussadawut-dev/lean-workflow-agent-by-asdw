# Queue and local ownership

[Back to README](../README.md)

Run CLI examples from the repository root.

Queue items add dependencies and exclusive scope ownership to full-mode work. Create the owning [tracker](tracker.md) before adding queue items.

## Claim work in full mode

Configure full mode, create a tracker, and create queue items from `.lean/templates/queue-item.json` under `.agents/queue/items/`. Each item needs a unique `QNNNN` ID, a valid tracker ID, dependencies and exclusive scope labels.

```sh
python3 .lean/scripts/workflow.py configure full
python3 .lean/scripts/workflow.py queue list
python3 .lean/scripts/workflow.py queue claim --id Q0001 --agent worker-a --request-id RANDOM-UNIQUE-ID
```

Replace `RANDOM-UNIQUE-ID` with a new random identifier of at least eight characters, such as a UUID. Keep it until you receive the claim receipt. If the response is lost, retry with the same agent, item and request ID to recover the same token. `claim-next` can select an eligible item when a particular ID has not been assigned.

The claim returns a token. Use it to renew or release ownership:

```sh
python3 .lean/scripts/workflow.py queue heartbeat --id Q0001 --token 'TOKEN-FROM-RECEIPT'
python3 .lean/scripts/workflow.py queue release --id Q0001 --token 'TOKEN-FROM-RECEIPT'
```

A lease lasts 30 minutes; renew it during long work. Use `queue complete --id Q0001 --token 'TOKEN-FROM-RECEIPT' --evidence 'ACTUAL-VALIDATION-EVIDENCE'` only after validation and required review. Completion rechecks dependencies and requires nonblank evidence; it cannot establish that an arbitrary evidence string is true. Synchronize the tracker after queue completion.

## Clean completed queue items

Use either command in your coding agent:

```text
/clean-queue old
/clean-queue all
```

| Command | DONE items selected | Items retained |
|---|---|---|
| `/clean-queue old` | Completed strictly more than 30 days ago, using `completed_at`. | DONE from the last 30 days, undated DONE, and all READY/BLOCKED items. |
| `/clean-queue all` | Every DONE item, including undated legacy items. | All READY/BLOCKED items. |

Both commands archive queue items only; trackers stay in place. “All” means all DONE items,
not all work. Cleanup moves records out of the active queue and keeps their full history.
The skill previews the selection, then applies the explicitly requested cleanup without asking
for the same permission again. If slash-command discovery is unavailable, follow the shared
[clean-queue procedure](../.claude/skills/clean-queue/SKILL.md) or use the CLI below.

Equivalent CLI commands (choose old or all):

```sh
python3 .lean/scripts/workflow.py clean-queue old --dry-run
python3 .lean/scripts/workflow.py clean-queue old --apply
python3 .lean/scripts/workflow.py clean-queue all --dry-run
python3 .lean/scripts/workflow.py clean-queue all --apply
python3 .lean/scripts/workflow.py queue history
python3 .lean/scripts/workflow.py queue history --id Q0001
```

New completions record a UTC `completed_at`. Old skips/reports legacy DONE items without that field;
all can archive them. Exactly 30 days old is retained by old; it becomes eligible only after that
threshold. File modification time is never used to invent a completion date.

History under `.agents/queue/history/` retains original JSON bytes, custom fields, evidence, IDs,
checksum, archive time and selection without automatic expiry. Commit this project history when
saving the cleanup; it is not template material. Dependencies and tracker checks resolve archived
DONE items, while the active queue list and claims exclude them. History can be read after lowering
the project mode. `queue history` lists archived IDs/titles; `queue history --id Q0001` returns
the full snapshot, including original JSON in its `content` field. A checksum detects content
mismatch; it is not proof of authentic evidence.

Preview writes nothing; apply uses the shared lock and rechecks data. Live claims on DONE records
and malformed data block cleanup. Valid live claims on retained READY items are preserved and do
not block it. Each snapshot is written/synced before deleting its source. A process
interruption can leave an identical source copy; it is already logically archived, and retrying
cleanup finishes the removal. Batches are recoverable per item, not all-or-nothing; report any
partial progress after an error. Do not reuse archived IDs, manually delete prerequisites, or run
cleanup alongside workers using older tooling. Neither the CLI nor skill commits/pushes automatically.

## Durable tracking and local ownership

Trackers retain acceptance criteria, decisions, status and evidence across sessions. Queue items link work to trackers and declare dependencies and exclusive scopes. The CLI validates IDs, supported states, dependency cycles, completion evidence and tracker–queue consistency where the active mode requires it.

Local lease tooling supports exact-item claims, eligible-item selection, heartbeat, release, completion and retry recovery. It refuses overlapping exact scope labels, multiple live claims for one agent and unfinished dependencies at completion. Configure, downgrade and worker operations use the same lock; workers check the current mode after acquiring it.

Scope labels are compared exactly: a directory label does not automatically cover all descendant file labels. Ownership is coordinated in **one checkout**, not across machines or Git worktrees. Tokens are coordination receipts, not a security boundary, and expired leases do not forcibly stop a worker process.
