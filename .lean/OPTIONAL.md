# Optional maintenance pack

Ordinary tasks use eight core procedures: init, task, scope, research, grill, multi-agent, review and gate. Maintenance skills are bundled as canonical resources, but are absent from runtime discovery by default. Their tools/tests remain installed so existing records, recovery and upgrades stay compatible.

Enable both runtimes' seven extra discovery links with `python3 .lean/scripts/skill_pack.py enable`; inspect with `status`, or remove only the links with `disable`. Conflicting custom slots block the batch. Canonical resources are retained. Reload runtime skills after changing discovery. This setting is independent of standard/tracker/full mode and direct/delegated execution.

Queue cleanup uses `/lean-clean-queue old` (DONE older than 30 days) or `/lean-clean-queue all` (all DONE). Preview/apply are available through `clean-queue old|all --dry-run|--apply`; original records move into project-owned queue history, not deletion. Trackers and unfinished items remain. Undated legacy DONE items are skipped by old. See `policy/WORKFLOW.md`.

Model research updates use `/lean-model-update codex|claude|all`. Preview is the default; explicitly approved apply updates an optional project-owned catalog and retains an ignored local catalog lock file. Session/global settings stay under runtime control. See `policy/MODELS.md`.

Use `/lean-clean-repo` to preview evidence-backed cleanup of generated clutter and obsolete project files, including exact reference updates. Matching plan approval permits guarded apply with external snapshots; restore refuses subsequent work. Preserve protected state and uncertain candidates, stop repository writers and validate/review before completion. See the shared skill and its tooling reference.

Use `/lean-compress` for concise, clear workflow prose. It inventories and fully reads all authorized workflow files before compression, preserves rules/protected content, previews by default and edits only approved targets.

Use `/lean-takeover-workflow "<target path>"` to audit an existing repository, resolve migration decisions through Grill, propose a concrete plan and install Lean after matching approval. Preview does not write to the target. External staging verifies the proposed public workflow before writes; snapshots/journals support resume and guarded rollback; APPLIED still requires the actual target gate and HIGH independent review. See the shared procedure and `CUSTOMIZING.md`.

Use `/lean-use-submodule <remote url>` to keep Lean as the superproject and application code in `targets/<repository-name>`. No workflow files are added to the application. Project facts/config and records live in `.lean/targets/<name>/`, using the existing record layout inside each directory. `submodule.py context` returns all three roots and the project file; default workflow/catalog commands select the active records, while `--root` is explicit. Selection is ignored checkout-local state; cloned workspaces initialize/select a registered target by rerunning the command. Application gates run in the target and block on missing checks; Claude runs them before its Lean cache, Codex runs them explicitly. See the shared procedure and `CUSTOMIZING.md`.

Use `/lean-update-workflow [--ref <tag|branch|commit>]` to update an existing Lean installation from the upstream stable tag. Preview pins the commit and audits local changes; approved apply uses external staging/snapshots and guarded recovery. Preserve project data, permissions and custom extensions. `.lean/upstream.json` is project-owned provenance, never a release asset.
