---
name: clean-queue
description: Archive completed queue items with /clean-queue old (completed over 30 days ago) or /clean-queue all (all DONE items). Preserve history and trackers.
---

Read `AGENTS.md` and `.lean/README.md`. Use the project root for the commands below.

- `old`: select DONE items whose timezone-aware `completed_at` is strictly more than 30 days ago. Legacy DONE items without a completion date are reported and retained; never infer age from file mtime or invent a date.
- `all`: select every DONE item, including legacy undated items. READY/BLOCKED items are never selected. Do not clean trackers, tokens, caches, or history.
- An explicit `/clean-queue old` or `/clean-queue all` authorizes that archive operation. If no selection is supplied, ask which one; do not broaden the requested selection. A request only to preview authorizes dry-run alone.

Run `python3 .lean/scripts/workflow.py clean-queue <old|all> --dry-run`. Inspect selected IDs, recovery removals and unknown-age IDs. If it succeeds and apply is authorized, run the same command with `--apply`; no repeated approval is needed. The tool takes the shared lock and rechecks current state. Never bypass an error with shell deletion, change DONE/evidence, or release another worker's claim to make cleanup pass.

History snapshots under `.agents/queue/history/` retain the original UTF-8 JSON bytes, IDs, evidence, custom fields, checksum, archive time and selection. They remain dependency/tracker evidence and are not claimable or shown in the active queue list. Keep history in project version control; it has no automatic expiry. This command does not commit or push.

Apply publishes each snapshot before removing its source. A process interruption may leave an identical source copy; it is logically archived, and retrying cleanup finishes its removal without changing history. A batch is per-item recoverable, not an all-or-nothing transaction. Stop and report errors; do not claim that a failed batch made no changes. Active claims on DONE records, malformed data or changed duplicate IDs block cleanup. Valid live claims on retained READY items are preserved and do not block cleanup. Do not hand-edit records concurrently or run workers using old tooling.

Run `python3 .lean/scripts/workflow.py check` after applying in full mode. Report archived IDs/count, unknown-age items, errors and recovery actions. Browse snapshots with `python3 .lean/scripts/workflow.py queue history` or `queue history --id QNNNN`. Missing files/invalid configuration are errors, not permission to reset the project mode.

$ARGUMENTS
