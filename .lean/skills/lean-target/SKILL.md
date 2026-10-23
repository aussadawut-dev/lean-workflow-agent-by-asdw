---
name: lean-target
description: Add or reuse a remote application repository as a Lean submodule, keeping workflow and work records out of it.
user-invocable: true
argument-hint: "<remote url>"
---

# Lean Target

Input: `$ARGUMENTS`, or the current task when substitution is unavailable. Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity; keep model reasoning effort separate.

Use `/lean-target <remote url>` from Lean. The application stays in `targets/<repository-name>` with no installed workflow files. One active target per session; do not switch during another task/active workset.

1. Read/reuse the Lean contract. Run `python3 .lean/scripts/submodule.py use --dry-run -- "<remote url>"`, passing the URL as one properly quoted argument, never interpolated shell code. No tokens/passwords in URLs. Inspect paths/staging; stop on collision, conflicting registration, symlink boundary or pending `.gitmodules` changes. Preserve existing checkouts/work. A direct request authorizes routine add/reuse/selection without repeated approval.
2. Run the same command with `--apply`, initializing only that submodule. Preserve attached branches and pending changes. Attach a clean detached checkout at its pinned commit: default branch if it points there, otherwise `codex/lean-<name>`. Never advance to remote latest/reset an existing branch. On branch failure preserve the partial checkout, resolve material choices with the user and retry; never remove Git metadata.
3. Read returned context and target instructions. `workflow_root` supplies policies/tools/templates; `project_root` supplies application commands/code/Git; `record_root` supplies PROJECT, configuration and work records. Preserve target requirements and start sessions from Lean. Invalid context blocks; never fall back to another root.
4. Fill `project_file` from observed facts and safe verified checks, leaving unknowns undefined. Read only relevant target guides/configuration and affected dependencies, not the whole application. Use `lean-init` for initial mode/execution, retaining accepted settings. Default workflow/catalog commands select active records; explicit records use `--root <record_root> --workflow-root <workflow_root>`, Lean configuration uses `--root <workflow_root>`. Queue scope labels name target files; records stay in record_root.
5. Verify selection with `python3 .lean/scripts/submodule.py context`. The generated target gate is empty; setup is not application validation. Once defined, run `python3 .lean/scripts/submodule.py gate` and Lean's gate. Lean workflow/catalog checks need explicit `--root <workflow_root>`. Claude Stop checks the application before Lean's cache; Codex runs both explicitly. Undefined/failed target checks block DONE for application work. Inspect application commands before executing repository code within task authority.
6. Report path, branch, PROJECT location, both Git statuses and check results/gaps. Addition stages `.gitmodules`/gitlink; no commit/push. Application commits belong to the target; Lean pointer changes need separate review. Never update other pointers. `python3 .lean/scripts/submodule.py clear` deselects without deleting checkout/records. Ignored selection is checkout-local; after cloning rerun with the registered URL.

Use delta context on retry: inspect current context/branch/partial setup before repeating mutations; reuse verified unchanged facts. Stop when selection and requested setup are verified, with unknown facts and missing application checks explicit; do not invent checks or expand into application implementation.

$ARGUMENTS
