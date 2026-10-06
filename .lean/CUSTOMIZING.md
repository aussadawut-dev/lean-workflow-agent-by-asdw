# Importing, customizing and upgrading

## Current authority

Baseline 3.4.0 uses `AGENTS.md` as the shared canonical contract. `CLAUDE.md` is a runtime entrypoint. The active agent leads unless project additions record a different Controller or primary agent. No provider-specific ownership, product stack or model shortlist is imposed.

Keep project facts, commands and gates in PROJECT; keep mode/execution in config; keep accepted scope and work records in the project's chosen tracking system. Project overrides go below the contract's Project additions marker. Record local workflow extensions in project-owned documentation (an existing LOCAL-EXTENSIONS file may serve this purpose). Do not edit portable policy per project without tracking that delta.

## Reusable assets and exclusions

Import policy, shared procedures, all matching Codex adapters, reviewer, hooks, generic templates, tooling and tests together. Merge settings, gitignore, CI and entrypoints. Keep `.lean/LICENSE` alongside your project's own license: the copied workflow retains its upstream copyright and permission notice. Attribution does not require replacing the project license.

Never copy another project's actual trackers, queue items, leases, gate caches/refusal markers, transcripts, credentials, project facts, application code or build artifacts. Tracker/full setup creates blank support guides/templates only. The repository ships standard/unconfigured/direct and no records; opting into delegated or full behavior is a separate explicit choice.

## Upgrade checklist

1. Read the new release's migration entry before replacing files. Save the project's canonical contract additions, runtime additions and local extension deltas.
2. Preserve the optional project model catalog and its accepted research evidence. Preserve PROJECT, config (including configured mode/execution), all accepted decisions and project record directories. Do not reset a configured repository or change the primary agent.
3. Update policy/router/changelog, all twelve shared procedures and their adapters, hooks/reviewer, mode tooling/templates and self-tests as a coherent set. Preserve project-specific extra skills and agents. Reconcile any existing local extensions, including scope/research/grill/delegation and model evidence gates.
4. Reapply shared overrides below AGENTS Project additions and Claude-specific overrides below CLAUDE Project additions. A project with another established canonical arrangement must reconcile it deliberately rather than silently lose its contract.
5. Merge settings and gitignore; never replace existing permissions with template defaults merely for convenience. Preserve application CI/gate and merge workflow checks. Keep `.agent-runtime/`, Claude gate files, Python caches and merge debris ignored.
6. Run the actual PROJECT Quality Gate and workflow checks that remain installed. Any behavior change needs meaningful tests; fixes demonstrate regression failure before repair and success after. Finish required independent review over the shipping delta.

## Taking over another workflow

Use `/lean-takeover-workflow "<target path>"` (Codex: `$lean-takeover-workflow`) for deliberate replacement of an existing agent workflow. Read the shared skill before proceeding. It fully reads authorized workflow dependencies, grills material choices with evidence and consequences, maps old rules/documents into Lean ownership and presents an exact plan before apply. Existing accepted choices are reused; clear mechanics do not need extra questionnaires.

The Python helper imports only the portable assets declared in the fingerprinted `.lean/assets.json` release registry. Adjacent local scripts/templates are not release assets. Regenerate and review the registry when changing the distribution; a pre-registry baseline needs that upgrade first. It does not synthesize project rules or merge permissions automatically. Reconcile target PROJECT/config, runtime settings, application gate/CI, custom capabilities, documentation routes and records in the reviewed plan. Preserve valid existing Lean trackers/queues; state transitions and downgrades retain their original tools and guards. Supported `casetodian-v1` foreign queue/tracker conversions use explicit decision-bound `record_migrations`, exact inert originals and validated staged records in the same recoverable journal. Cancelled records become reserved cancellation history; they never become DONE. Existing Lean records remain protected. Unsupported foreign-record mappings or unresolved authority conflicts block the affected migration.

Keep private session artifacts outside both repositories. Snapshots archive original public workflow content without leaving active instruction filenames in the target. Do not add a blanket history exemption to active structure checks; version-controlled history requires inert content and deliberate runtime/reference routing. Preview/check/stage/seal leave the target intact. Validate the staged public workflow before sealing; it excludes private/generated/application dependencies and does not replace the actual target gate. Apply may create the local queue lock; resume uses the same sealed plan, and rollback refuses subsequent edits. File-write success is APPLIED until the target's checks and HIGH independent review pass. No commit, push, global configuration or paid usage is implied.

## Existing 2.x projects

Move shared CLAUDE contract rules into AGENTS while preserving project-specific additions. Make CLAUDE import AGENTS; retain runtime-specific additions there. Older customized AGENTS or local mode extensions must be compared before replacement. Structure checking supports a legacy AGENTS import of CLAUDE during migration, but do not leave two competing contracts.

For repositories without config, use `/lean-init` to choose mode and execution. Previously configured tracker/full repositories retain their config and records; adding the optional execution field defaults to direct when absent. If a project already requires Controller/worker delegation, configure delegated and preserve that accepted rule. Do not downgrade modes automatically. For an explicitly requested downgrade, preview with `downgrade <lower-mode> --dry-run`, resolve blockers, then use `--apply` (plus `--keep-pending` for acknowledged paused work). Preserve records and expired leases; never bypass active-work checks. Stop old-tooling workers before upgrading; use the current CLI for transitions.

## Queue history

Cleanup archives DONE queue items only. Preserve `.agents/queue/history/` with project records
and version-control it; no history is shipped in this template or imported from another project.
Update mode tooling and all procedures/adapters before cleanup, stop old-tooling workers, and do
not manually reuse IDs or remove archived prerequisites. History has no automatic expiry and
remains readable by `queue history` after lowering the mode. Tracker archival is not implemented.

## Runtime limits

Bash, Git and Python 3.9+ are required for checks/tooling; leases use Unix fcntl. Supported hosts are macOS, Linux and WSL, not native Windows. Codex adapters reference shared procedures but do not install Claude hooks or permissions into Codex. Runtime model and effort options must be checked at dispatch; unavailable metadata is recorded honestly. Exact scope labels coordinate files in one checkout; directory containment or cross-worktree lease protection is not implied.
