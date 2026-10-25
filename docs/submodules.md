# Application submodules

[Back to README](../README.md)

Run the CLI examples from the Lean repository root.

Use a submodule when you want application code in its own repository and Lean's workflow files outside it. After enabling optional skills, run `/lean-target <remote url>` in Claude or `$lean-target <remote url>` in Codex. It adds or reuses the application under `targets/<repository-name>`.

Lean keeps `.gitmodules`, the gitlink and all workflow/project records. The command installs no agent workflow files in the application.

```sh
# Preview first; use --apply for the requested installation.
python3 .lean/scripts/submodule.py use --dry-run -- https://github.com/team/my-project.git
python3 .lean/scripts/submodule.py use --apply -- https://github.com/team/my-project.git
python3 .lean/scripts/submodule.py context
```

## Use the right root

Start sessions from Lean. The context command tells you which root to use:

| Root | Use it for |
|---|---|
| `project_root` | Application code, commands and Git operations. |
| `record_root` | Project facts, configuration, trackers and queue records. |
| `workflow_root` | Lean rules and tools. |

Workflow, model-catalog and skill-effort commands select active target records by default. `--root` overrides the selection. Explicit workflow record operations can add `--workflow-root` to use Lean's templates.

Fill the returned project file with verified application checks, then run `python3 .lean/scripts/submodule.py gate`. Keep Lean self-checks separate. Claude runs target checks before using its Lean cache; Codex runs target checks explicitly and also checks Lean for workflow changes.

The standalone target gate and both runtime adapters check retained target gate controls before running application commands. Switching the active target does not approve changed controls. Use the existing control-acceptance procedure only for an already approved change; an upgrade that protects an additional control may also need that recorded acceptance.

High-risk paths come from each retained target's project file and apply to its application files, even after clearing or switching selection. The review receipt remains in Lean's `.agent-runtime/review.json` and covers the whole shipping state, including target contents. Runtime sessions retain their original commit boundary; pass `--session <existing-session-id>` to a direct target gate to use that boundary after committing application work and its parent gitlink. A later target edit invalidates the receipt.

## Keep Git changes clear

Adding a submodule stages its registration but does not commit or push. Initializing a registered submodule keeps its pinned commit. If the default branch differs, the command creates `codex/lean-<name>` at that commit instead of advancing the pointer.

Commit application work inside the target. Review Lean's resulting pointer change separately. Active selection is checkout-local and ignored; after cloning Lean, rerun the command to initialize/select the registered target.

`python3 .lean/scripts/submodule.py clear` deselects a target and keeps its checkout and records. Live claims or active trackers block switching. Use one active target per session. Adopting an existing checkout, removing workflow from target history and automatically publishing pointer changes are outside this command's scope.
