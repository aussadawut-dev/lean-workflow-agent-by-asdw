# Importing, customizing and upgrading

## Current authority

Baseline 3.2.0 uses `AGENTS.md` as the shared canonical contract. `CLAUDE.md` is a runtime entrypoint. The active agent leads unless project additions record a different Controller or primary agent. No provider-specific ownership, product stack or model shortlist is imposed.

Keep project facts, commands and gates in PROJECT; keep mode/execution in config; keep accepted scope and work records in the project's chosen tracking system. Project overrides go below the contract's Project additions marker. Record local workflow extensions in project-owned documentation (an existing LOCAL-EXTENSIONS file may serve this purpose). Do not edit portable policy per project without tracking that delta.

## Reusable assets and exclusions

Import policy, shared procedures, all matching Codex adapters, reviewer, hooks, generic templates, tooling and tests together. Merge settings, gitignore, CI and entrypoints. Keep `.lean/LICENSE` alongside your project's own license: the copied workflow retains its upstream copyright and permission notice. Attribution does not require replacing the project license.

Never copy another project's actual trackers, queue items, leases, gate caches/refusal markers, transcripts, credentials, project facts, application code or build artifacts. Tracker/full setup creates blank support guides/templates only. The repository ships standard/unconfigured/direct and no records; opting into delegated or full behavior is a separate explicit choice.

## Upgrade checklist

1. Read the new release's migration entry before replacing files. Save the project's canonical contract additions, runtime additions and local extension deltas.
2. Preserve PROJECT, config (including configured mode/execution), all accepted decisions and project record directories. Do not reset a configured repository or change the primary agent.
3. Update policy/router/changelog, all nine shared procedures and their adapters, hooks/reviewer, mode tooling/templates and self-tests as a coherent set. Preserve project-specific extra skills and agents. Reconcile any existing local extensions, including scope/research/grill/delegation and model evidence gates.
4. Reapply shared overrides below AGENTS Project additions and Claude-specific overrides below CLAUDE Project additions. A project with another established canonical arrangement must reconcile it deliberately rather than silently lose its contract.
5. Merge settings and gitignore; never replace existing permissions with template defaults merely for convenience. Preserve application CI/gate and merge workflow checks. Keep `.agent-runtime/`, Claude gate files, Python caches and merge debris ignored.
6. Run the actual PROJECT Quality Gate and workflow checks that remain installed. Any behavior change needs meaningful tests; fixes demonstrate regression failure before repair and success after. Finish required independent review over the shipping delta.

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
