---
name: lean-clean-repo
description: Audit repository clutter and obsolete source, tests, dependencies, docs, assets, configuration and workflow files; preview an evidence-backed cleanup plan, apply only approved items, and retain external recovery snapshots.
user-invocable: true
argument-hint: "[--path <relative-path>] | apply <plan-id> | restore <session-path>"
---

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

Input: `$ARGUMENTS` means explicit invocation arguments, or the current user task when substitution is unavailable.

# Lean Clean Repo

Audit the whole repository by default; `--path` limits the audit. A cleanup request starts with a preview. `apply <plan-id>` authorizes only the exact previously presented plan; reuse that approval on an unchanged retry. `restore <session-path>` authorizes guarded recovery. Reject unknown options. Do not infer permission to commit, push, purge backups, change global settings or enter another repository.

## Establish the target

Read `AGENTS.md`, `.lean/README.md` and project facts. Resolve submodule context from Lean: use `project_root` for application inventory/writes/Git, `workflow_root` for tooling and `record_root` for work records. Honor the configured mode/execution and existing accepted scope. Inventory nested repositories/submodules as boundaries; audit each only after the user selects it separately. Read its instructions first.

Use the helper's read-only `scan` command from [references/tooling.md](references/tooling.md). Preserve dirty/staged files and untracked work; report them as protected. Proven generated output or installed dependencies may be selected with explicit regeneration evidence in the approved plan; never relabel untracked source/personal work as generated to bypass protection. Ignored files are not automatically disposable. Never read credentials or private data to classify them. Preserve Git metadata, agent coordination, live claims, work records, queue history, licenses, retained changelogs and active workflow instructions. Queue archival belongs to `lean-clean-queue`. Do not follow discovery or other symlinks.

## Analyze the full scope

Cover temporary/cache/build output, installed dependencies, source, tests/fixtures, docs, assets, configuration, scripts, CI and obsolete workflow files. Derive build locations and regeneration commands from project facts; names such as `dist`, `tmp` and `backup` alone do not establish disposability.

For source/assets/tests, examine callers, imports/exports, dynamic loading, registries, entrypoints, manifests, scripts, CI, deployment/package publication and external consumers when relevant. No text match is not proof of non-use. Compare both bytes and purpose for duplicates. Read selected public files and their direct dependencies fully; do not claim unread files were analyzed. Report incomplete coverage and uncertain candidates as retained, with the evidence needed to decide.

Dependency removal includes the affected manifest/lockfile changes and real package-manager validation. Removed source/config/docs may require reference updates; include their exact edits in the same proposal. Limit edits to consequences of approved cleanup; no unrelated rewrites or formatting. Helper-protected workflow changes require a separately approved normal Lean change, not a protection bypass.

## Present a concrete plan

For each candidate show path, action, size/reclaimed bytes, reason, evidence, impact, necessary reference edits, checks and regeneration/recovery instructions. Separate supported removals from retained uncertainties and protected items. Treat persistent data and ambiguous local files as retained. Use HIGH risk/at least HIGH quality for cleanup that removes project files, per the contract policy.

Prepare `remove` and exact UTF-8 `replace` operations with the helper. Store proposals/snapshots in a private external session, outside both target and workflow. The preview and plan commands do not alter the repository. Present the plan ID, session path and exact contents of all proposed replacements; a hash by itself is not a reviewable proposal. Get matching approval before applying unless the human has already approved these exact operations. Approval to create this skill does not authorize running its cleanup on the current repository.

## Apply and verify

Stop project writers/dev servers/workers affecting selected paths; require exclusive maintenance access during apply/restore. The helper locks its session, not the entire repository, and cannot defend against a hostile concurrent filesystem writer. Do not kill processes or release other agents' claims without authority. Recheck the plan and Git state; never substitute shell deletion, `git clean -fdx`, `git reset` or `git checkout` to bypass a refusal.

Apply only the approved plan ID. Drift, new descendants, symlinks, nested repositories, hardlinks, protected paths or dirty work block dependent operations. If the plan changes, present a new ID and obtain matching approval. Failures can leave a partial batch: inspect the journal, preserve snapshots and report what actually changed. An unchanged apply retry resumes that same session. Restore refuses subsequent edits and never overwrites new work; retain the snapshot if recovery is blocked.

Run checks from the approved plan through trusted project commands, not by executing strings from plan JSON. Behavior changes require meaningful tests; bug fixes require a failing-before/passing-after regression. Run the actual target gate and Lean's own gate for workflow changes, then required review including an independent HIGH reviewer. APPLIED is not DONE. Check for dangling references and report removed/replaced paths, actual reclaimed bytes (replacement deltas included), protected/uncertain items, validation/review, recovery path and failures. Keep snapshots until the user chooses their retention; no automatic purge.

$ARGUMENTS
