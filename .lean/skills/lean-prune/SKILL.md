---
name: lean-prune
description: Archive completed queue items or audit and clean obsolete repository files with recovery snapshots; preview by default for repo cleanup.
user-invocable: true
argument-hint: "queue <old|all> [--days N] [--preview] | repo [--path <relative-path>] | repo apply <plan-id> | repo restore <session-path>"
---

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

Input: `$ARGUMENTS` means explicit invocation arguments, or the current user task when substitution is unavailable.

# Lean Prune

Select the target from `$ARGUMENTS`: `queue` archives completed queue records into history; `repo` audits and cleans obsolete repository files with external recovery snapshots. If neither target is specified, ask which one to run and never guess or broaden the selection. Reject unknown options. Neither mode commits, pushes, purges backups, changes global settings or enters another repository.

## Queue archival (`queue <old|all> [--days N] [--preview]`)

Read `AGENTS.md` and `.lean/README.md`, and use the project/record root without reading `references/tooling.md`.

- `old` selects DONE items whose timezone-aware `completed_at` is strictly more than N days ago (default 30; `--days N` is a positive whole number and invalid with `all`). Legacy DONE items without `completed_at` are reported and retained; never infer age from file mtime or invent dates.
- `all` selects every DONE item, including undated legacy items. READY/BLOCKED items, trackers, tokens, caches and history are never touched.
- An explicit `queue old` or `queue all` authorizes that archive operation; `--preview` authorizes dry-run only. Run `python3 .lean/scripts/workflow.py clean-queue <old|all> [--days N] --dry-run`. Inspect selected IDs, recovery removals and unknown-age IDs. If it succeeds and apply is authorized, run the same command with `--apply` without asking again.
- Snapshots under `.agents/queue/history/` retain original UTF-8 JSON bytes, IDs, evidence, custom fields, checksum, archive time and selection in version control as non-claimable dependency/tracker evidence. Apply publishes each snapshot before removing its source and is per-item recoverable; retrying finishes an interrupted removal. Active claims on DONE records, malformed data or changed duplicate IDs block cleanup, while valid live claims on READY items are preserved. Never bypass errors with shell deletion or alter DONE/claim state. Run `python3 .lean/scripts/workflow.py check` after applying in full mode and report archived IDs/count, unknown-age items, errors and recovery (`queue history [--id QNNNN]`).

## Repository cleanup (`repo [--path <relative-path>] | repo apply <plan-id> | repo restore <session-path>`)

Read `AGENTS.md`, `.lean/README.md`, project facts and [references/tooling.md](references/tooling.md). Resolve submodule context from Lean (`project_root` for application inventory/writes/Git, `workflow_root` for tooling, `record_root` for work records). Treat nested repositories/submodules and symlinks as boundaries; audit a nested repository only when selected separately.

- Start with the helper's read-only `scan` (whole repository by default, or `--path`). Preserve dirty/staged/untracked work, credentials, Git metadata, coordination/live claims, work records, queue history, licenses, retained changelogs and active workflow instructions. Only proven generated output or installed dependencies with verified regeneration commands in the approved plan may be selected; never relabel untracked source or personal work as generated.
- Analyze callers, imports/exports, dynamic loading, registries, entrypoints, manifests, scripts, CI and external consumers across code, tests, docs, assets and config. No text match is not proof of non-use. Read selected public files and direct dependencies fully; retain uncertain or partially covered candidates with the evidence needed to decide. Include exact manifest/lockfile and reference `replace` edits in the same proposal. Use HIGH risk and at least HIGH quality when removing project files.
- Prepare `remove` and exact UTF-8 `replace` operations in a private external session outside target and workflow. Present path, action, reclaimed bytes, reason, evidence, impact, exact replacement contents, checks, plan ID and session path. Obtain matching approval before `repo apply <plan-id>` (reuse on an unchanged retry); `repo restore <session-path>` performs guarded recovery and refuses subsequent edits.
- Stop repository writers affecting selected paths during apply/restore. Never substitute shell deletion, `git clean -fdx`, `git reset` or `git checkout` to bypass a refusal. Run approved checks through trusted project commands, then target/Lean gates and required review including an independent HIGH reviewer before DONE. Report removed/replaced paths, reclaimed bytes, retained/protected items, validation/review and the recovery session path.

$ARGUMENTS
