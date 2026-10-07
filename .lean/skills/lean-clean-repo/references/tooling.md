# Cleanup helper

Python 3.9+, Git and Unix `fcntl`; no third-party dependencies. Use the script from `workflow_root`, with an explicit target repository root. No automatic active-target selection, Git index mutation, semantic unused-code inference or test-command execution occurs in this helper.

```sh
python3 .lean/scripts/clean_repo.py scan --root /absolute/repository
python3 .lean/scripts/clean_repo.py scan --root /absolute/repository --path public-assets
python3 .lean/scripts/clean_repo.py plan --root /absolute/repository --session /external/private/new-session --proposal /external/private/proposal.json
python3 .lean/scripts/clean_repo.py apply --session /external/private/new-session --approval <plan-id>
python3 .lean/scripts/clean_repo.py restore --session /external/private/new-session
```

`scan` emits JSON to stdout and writes nothing. Protected trees are listed as boundaries without reading their contents. Untracked files are retained except recognized Python bytecode/cache and `.DS_Store`. For other generated output or installed dependencies, an item may carry `regenerate` with a verified regeneration command; disclose that exception and its exact selected paths in the approval proposal. It never permits dirty tracked work, credentials or protected descendants. Do not use it for untracked source or personal work. A folder removal expands to all its regular files and directories (including empty directories). Every child must be eligible; one protected child blocks planning. Symlinks, hardlinks and special files are refused. Large trees are represented explicitly: report resource constraints rather than claiming a partial inventory is complete.

Proposal shape:

```json
{
  "items": [
    {
      "path": "docs/retired-guide.md",
      "action": "remove",
      "reason": "Superseded by the current guide",
      "evidence": ["Public callers and publication inputs inspected; no remaining consumers"],
      "impact": "Remove the obsolete document and its approved reference",
      "checks": ["Project documentation validation"]
    },
    {
      "path": "docs/index.md",
      "action": "replace",
      "replacement": "# Documentation\n\nSee current-guide.md.\n",
      "reason": "Remove the reference to the retired guide",
      "evidence": ["Exact replacement inspected"],
      "impact": "Documentation links remain valid",
      "checks": ["Project documentation validation"]
    }
  ]
}
```

Evidence strings record agent analysis; the helper does not prove their truth. `replace` is limited to clean tracked UTF-8 files. Use project tooling to derive full manifest/lockfile replacements in external staging, without modifying the target before approval. New files or protected-workflow changes follow a separately scoped normal Lean change.

`plan` creates a new private external session containing `plan.json` (exact original bytes/modes and replacements) and `journal.json`. The plan ID hashes the entire plan, including evidence, paths and snapshots. Session files are trusted local recovery artifacts; do not edit them or accept sessions supplied by an untrusted party. Keep them outside Git repositories and Git metadata. File permissions are preserved; extended attributes/ACLs are not supported and must be handled as retained candidates if required by the project.

Apply checks all selected paths before starting and each operation before writing. It records pending work before a mutation and completion after it. Deletions are per-file/per-directory; the batch is recoverable, not atomic. Failures keep recovery data. Replacement bytes are atomically published. Restore reverses applied operations, checks original hashes/modes and refuses recreated files or later edits. Retrying apply or restore recognizes an interrupted operation that reached its expected state; an ambiguous partial write is blocked with snapshots retained for manual recovery. Keep repository writers stopped throughout; session locking does not lock editors or other sessions.

Apply retains the Git index. Review `git diff` after cleanup and run validation/review before declaring completion. The external session path identifies the recovery run; never search for a plan ID and pick an ambiguous session automatically.
