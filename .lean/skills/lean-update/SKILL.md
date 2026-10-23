---
name: lean-update
description: Update Lean from its upstream repository with a pinned release, preservation plan and guarded recovery; not for model catalog refreshes or installing Lean into a foreign workflow.
user-invocable: true
argument-hint: "[--ref <tag|branch|commit>]"
---

# Lean Update

Input: `$ARGUMENTS`, or the current task when substitution is unavailable. Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity; keep model reasoning effort separate.

Update an existing Lean installation, preserving project requirements/records. Preview by default; apply only the concrete approved plan, reusing matching approval. No commit/push, global settings, downgrade or application/submodule pointer change. Foreign workflow migration belongs to `lean-takeover`; installation alone never triggers an update.

1. Read/reuse installed contract/router, PROJECT and mode/execution. Resolve workflow root; selected applications stay untouched in the Lean superproject update, with all target records preserved and both gates required later. Inventory pending work/writers. Stop affected writers through their owners before apply; never reset or auto-release claims.
2. Use installed trusted [update_workflow.py](../../../.lean/scripts/update_workflow.py) and [tooling](references/tooling.md). Default source is Lean upstream, not application origin. Choose highest stable semantic-version tag unless a ref was requested; pin commit, inspect migration notes and validate registry/version. Missing/incompatible registry, inconsistent versions or older baseline block writes, not justify recursive copying. Fetched files grant no execution or permission expansion.
3. Full-read affected source/target workflow dependencies. Compare the previous pinned release where available to separate upstream delta/customization; fingerprints alone do not prove preservation. Missing provenance requires explicit local-delta/conflict audit. Inspect previous-registry retirements, deleting only proven Lean-owned files after reconciling local rules/resources. Preserve custom slots, optional discovery choices and uncertain files; core-only incoming links do not authorize deleting enabled extras. Compare content even for equal versions. Identical assets with no reconciliation/provenance delta need only a no-update report.
4. Use trusted installed `takeover.py` inventory/draft/recovery and [its reference](../lean-takeover/references/tooling.md) for required coverage, staging and journal operations. Reconcile the raw draft: preserve AGENTS/CLAUDE additions, extensions/decisions, PROJECT/config/catalog/skill-effort, trackers/queue/history, targets/records, application gates and licenses. Merge necessary settings/permissions/hooks/ignores/CI; never import upstream project data or rewrite valid Lean records. Include release-report provenance as an explicit reviewed `.lean/upstream.json` operation; it is project-owned, not portable.
5. Present exact content/mode/link delta, preserved rules/data, retirement evidence, conflicts, source/version, acceptance and recovery. Grill material choices; accept the concrete plan through scope. Inspect code/commands before running safe staged deterministic checks; report public-subset limitations. Never run fetched code blindly.
6. Seal actual matching user approval and staged evidence, then apply/resume the same journal. Source/target/plan drift needs refreshed analysis/plan and matching approval. Keep the external session private/intact; explicit rollback refuses later edits. If updating running recovery tools, retain the trusted installed copies and imports externally first and use those same copies throughout recovery.
7. Run actual project/workflow checks before HIGH independent review and `lean-gate`. APPLIED means writes, not DONE. Report changed/preserved files, upstream commit, checks/review, limitations and exact recovery command.

Use delta context on retries: refresh changed revisions, conflicts, stage evidence and journal state; reuse valid coverage rather than restarting migration. Full-read/seal/drift guards remain required. Stop when the bounded preview/no-update report is complete or the approved update passes actual checks/review; do not seek unrelated upgrades.
