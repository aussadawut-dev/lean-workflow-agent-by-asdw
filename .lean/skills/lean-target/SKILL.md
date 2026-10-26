---
name: lean-target
description: Add or reuse a remote application repository as a Lean submodule, keeping workflow and work records out of it.
user-invocable: true
argument-hint: "<remote url>"
---

# Lean Target

Input: `$ARGUMENTS`, or the current task when substitution is unavailable. Resolve procedure intensity under `.lean/policy/SKILL-EFFORT.md` and state it; keep model reasoning effort separate.

Use `/lean-target <remote url>` from Lean. The application stays in `targets/<repository-name>` with no installed workflow files. One active target per session; do not switch during another task or active workset.

1. Read/reuse the Lean contract. Run `python3 .lean/bin/lean target use --dry-run -- "<remote url>"`, passing the URL as one quoted argument, never interpolated shell code. No tokens or passwords in URLs. Inspect paths and staging; stop on a collision, conflicting registration, symlink boundary or pending `.gitmodules` changes. Preserve existing checkouts and work. A direct request authorizes routine add/reuse/selection without repeated approval.
2. Run the same command with `--apply`, initializing only that submodule. Preserve attached branches and pending changes. A clean detached checkout is attached at its pinned commit: the default branch if it points there, otherwise `codex/lean-<name>`. Never advance to the remote's latest or reset an existing branch. On branch failure preserve the partial checkout, resolve material choices with the user and retry; never remove Git metadata.
3. Read the returned context and the target's own instructions. `workflow_root` supplies policies, tools and templates; `project_root` supplies application commands, code and Git; `record_root` supplies PROJECT, configuration and work records. Start sessions from Lean. An invalid context blocks; never fall back to another root.
4. Fill `project_file` from observed facts and safe verified checks, leaving unknowns undefined. Read only relevant target guides, configuration and affected dependencies. Use `lean-init` for the target's mode and execution. `lean mode|tracker|queue|effort|models` select the active target's records by default; `--root <record_root> --workflow-root <workflow_root>` names them explicitly, and Lean's own records use `--root <workflow_root>`. Queue scope labels name target files; records stay in record_root.
5. Verify with `python3 .lean/bin/lean target context`. The generated target gate is empty; setup is not application validation. Once defined, run `python3 .lean/bin/lean target gate` and Lean's gate (`lean gate run`, which also runs the target's checks first). Claude's Stop checks the application before Lean's cache; Codex and agy run both explicitly. Undefined or failed target checks block DONE for application work. Inspect application commands before executing repository code within task authority.
6. Report path, branch, PROJECT location, both Git statuses and check results or gaps. Adding stages `.gitmodules` and the gitlink; no commit or push. Application commits belong to the target; Lean pointer changes need separate review. Never update other pointers. `python3 .lean/bin/lean target clear` deselects without deleting the checkout or records. Selection is ignored, checkout-local state; after cloning, rerun `use` with the registered URL.

Use delta context on retry: inspect the current context, branch and partial setup before repeating mutations; reuse verified unchanged facts. Stop when selection and requested setup are verified, with unknown facts and missing application checks explicit; do not invent checks or expand into application implementation.

$ARGUMENTS
