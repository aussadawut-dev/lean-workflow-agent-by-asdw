---
name: lean-prune
description: Archive completed queue items or audit and clean obsolete repository files with recovery snapshots; preview by default for repo cleanup.
user-invocable: true
argument-hint: "queue <old|all> [--days N] [--preview] | repo [--path <relative-path>] | repo apply <plan-id> | repo restore <session-path>"
---

# Lean Prune

Input: `$ARGUMENTS`, or the current task when substitution is unavailable. Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity; keep model reasoning effort separate.

Select `queue` or `repo`; ask if omitted and reject unknown options. Do not broaden the selection. Neither mode commits, pushes, purges backups, changes global settings or enters another repository. Reuse AGENTS/router and valid project context; use delta context on retries, checking changed selections and operation state before repeating writes.

## Queue archival (`queue <old|all> [--days N] [--preview]`)

Use the selected record root. Do not load repository-cleanup tooling or scan application files for queue archival.

- `old`: DONE with timezone-aware `completed_at` strictly older than N days (default 30; positive whole number, invalid with `all`). Report/retain undated legacy items; never infer timestamps from mtime.
- `all`: every DONE item, including undated ones. Preserve READY/BLOCKED items, trackers, tokens, caches and history.
- Explicit `queue old`/`queue all` authorizes archival; `--preview` only authorizes dry-run. Run `python3 .lean/scripts/workflow.py clean-queue <old|all> [--days N] --dry-run`; inspect IDs, recovery removals and unknown ages, then use `--apply` if authorized without asking again.
- Snapshots in versioned `.agents/queue/history/` retain original UTF-8 JSON, IDs, evidence, custom fields, checksum, archive time and selection as non-claimable dependency/tracker evidence. Snapshot precedes source removal; retry finishes interrupted removal. Active DONE claims, malformed records or changed duplicate IDs block; valid READY claims stay intact. Never bypass errors with deletion or DONE/claim edits.
- After apply in full mode run `python3 .lean/scripts/workflow.py check`. Report archived IDs/count, unknown ages, errors and recovery (`queue history [--id QNNNN]`). Stop when selected archival and applicable checks finish or a specific record blocks it.

## Repository cleanup (`repo [--path <relative-path>] | repo apply <plan-id> | repo restore <session-path>`)

Read project facts and [tooling](references/tooling.md). For submodules resolve context: application/Git in `project_root`, tools in `workflow_root`, records in `record_root`. Nested repos/submodules and symlinks are boundaries; inspect nested repos only when separately selected.

1. Run read-only `scan`, bounded by `--path` when supplied. Preserve dirty/staged/untracked work, credentials, Git/coordination/claims, records/history, licenses, retained changelogs and active workflow instructions. Only proven generated output or installed dependencies with verified regeneration in the approved plan qualify; untracked source/personal work never does.
2. Trace candidate consumers through callers, imports/exports, dynamic loading, registries, entrypoints, manifests/lockfiles, scripts/CI, docs/assets/config and external consumers. Fully read selected public files/direct dependencies. No text match is not proof of non-use; retain uncertain or partially covered candidates. Include exact reference/manifest/lockfile `replace` edits. Removing project files requires HIGH risk and at least HIGH quality.
3. Prepare exact `remove`/UTF-8 `replace` operations in a private external session outside workflow/target. Present paths/actions, bytes, reasons/evidence, impact, replacement contents, checks, plan ID and session path. Obtain matching approval before `repo apply <plan-id>`; reuse unchanged retries. `repo restore <session-path>` refuses later edits.
4. Stop affected repository writers for apply/restore. Do not bypass refusals with shell deletion, `git clean -fdx`, `git reset` or `git checkout`. Run approved trusted checks, target/Lean gates and required independent HIGH review. Report changes/bytes, retained candidates, validation/review and recovery session.

Stop when the bounded proposal is reviewable (preview), or approved operations and verification finish; report partial failures with recovery intact. Do not expand cleanup to find more deletions.

$ARGUMENTS
