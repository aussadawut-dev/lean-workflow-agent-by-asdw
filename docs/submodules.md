# Application submodules

[Back to README](../README.md)

Run CLI examples from the repository root.

Run `/lean-use-submodule <remote url>` from Lean to add or reuse the application under `targets/<repository-name>`. Lean stores `.gitmodules`, the gitlink and all workflow/project records; the application receives no agent workflow files. The command uses one shared skill discovered by both runtimes.

```sh
# Read-only preview; the skill applies a direct installation request.
python3 .lean/scripts/submodule.py use --dry-run -- https://github.com/team/my-project.git
python3 .lean/scripts/submodule.py use --apply -- https://github.com/team/my-project.git
python3 .lean/scripts/submodule.py context
```

Start sessions from Lean. The context reports `project_root` for application commands and Git, `record_root` for project facts/config and tracking, and `workflow_root` for tools/rules. Default workflow, model-catalog and skill-effort commands select the active records; `--root` overrides that selection. Explicit workflow record operations can add `--workflow-root` to source templates from Lean. Fill the returned project file with verified application checks, then run `python3 .lean/scripts/submodule.py gate`; Lean self-checks remain separate. Claude runs target checks before using its Lean cache, while Codex runs both gates explicitly.

Adding a submodule stages its registration; it does not commit or push. Initializing a registered submodule preserves its pinned commit: if the default branch differs, the command creates `codex/lean-<name>` at that commit rather than advancing the pointer. Commit application work inside the target and review the resulting pointer change in Lean separately. Checkout-local selection is ignored: after cloning Lean, rerun the command to initialize/select the registered target. `python3 .lean/scripts/submodule.py clear` deselects without removing its checkout or records. Live claims/active trackers block switching; use one active target per session. Existing checkout adoption, workflow removal from target history, and automatic pointer publishing are not part of this command.
