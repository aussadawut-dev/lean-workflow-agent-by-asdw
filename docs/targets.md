# Application targets (submodules)

[Back to README](../README.md)

Run the examples from the Lean repository root.

Use a target when you want application code in its own repository and Lean's workflow files outside it. Run `/lean-target <remote url>` (Codex: `$lean-target`). It adds or reuses the application under `targets/<repository-name>`. Lean keeps `.gitmodules`, the gitlink and all workflow and project records; nothing is installed in the application.

```sh
python3 .lean/bin/lean target use --dry-run -- https://github.com/team/my-project.git
python3 .lean/bin/lean target use --apply -- https://github.com/team/my-project.git
python3 .lean/bin/lean target context
```

## Use the right root

| Root | Use it for |
|---|---|
| `project_root` | Application code, commands and Git operations. |
| `record_root` | Project facts, configuration, trackers and queue records (`.lean/targets/<name>/`). |
| `workflow_root` | Lean rules and tools. |

`lean mode`, `tracker`, `queue`, `effort` and `models` select the active target's records by default; `--root` overrides the selection, and `--workflow-root` supplies Lean's templates to an explicit record root. Lean's own gate lines pass `--root .` so they check Lean's records while a target is selected.

`status`, `watch`, `progress`, `gate` and `evidence` use the workflow root by default. Status reports its gate/progress scope, all three roots, and workspace and selected-target modes separately (`scope_root`, `roots`, `target_mode` in JSON). An explicit `--root` scopes those commands to that directory; a record-root status therefore need not contain the workspace's progress or shared gate result. `mode context` follows target records but reads gate/progress from the workflow root. Canonical `.lean/targets/<name>` record paths resolve that runtime root automatically; for separately located records, supply `--workflow-root`.

After the shared gate passes, close a tracker with `lean tracker status --id TCKNNN --status DONE --contract '<exact Task Contract>' --evidence '<acceptance and validation evidence>'` (a bound session contract may replace the flag). Closure requires that exact contract's recorded shared pass and required review, covering the workspace and target shipping content. A target-only gate does not supply a shared pass. Queue implementation completion remains independent of workset closure.

Fill the returned project file with verified application checks, then run `python3 .lean/bin/lean target gate`. `lean gate run` and both providers' Stops run the target's checks before Lean's own (before Lean's cache could skip them); agy runs them explicitly.

Target gate blocks are protected controls, checked before any application command runs; switching the selection does not approve changed controls. High-risk paths come from each retained target's project file and apply to its application files, even after clearing or switching the selection. The review receipt stays in Lean's `.agent-runtime/` and covers the whole shipping state, target contents included; a later target edit invalidates it. Pass `--session <id>` to a direct target gate to use a session's original commit boundary.

## Keep Git changes clear

Adding a target stages its registration but does not commit or push. Initializing a registered target keeps its pinned commit; if the default branch has moved, the command creates `codex/lean-<name>` at the pinned commit instead of advancing the pointer. Commit application work inside the target and review Lean's resulting pointer change separately. The selection is checkout-local and ignored; after cloning Lean, rerun `use` to initialize and select a registered target.

`lean spawn run` refuses while a target is selected: its worktrees are of the Lean workspace and would not contain the application. Spawn in-session subagents from `lean spawn plan` for target work.

`python3 .lean/bin/lean target clear` deselects a target and keeps its checkout and records. Live claims or active trackers block switching. Use one active target per session.
