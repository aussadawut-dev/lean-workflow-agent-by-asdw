---
name: lean-update
description: Update Lean from its upstream repository with a pinned release, a preview plan, snapshots and rollback; migrates 4.x installations to v5.
user-invocable: true
argument-hint: "[--ref <tag|branch|commit>]"
---

# Lean Update

Input: `$ARGUMENTS`, or the current task when substitution is unavailable. Resolve procedure intensity under `.lean/policy/SKILL-EFFORT.md`; keep model reasoning effort separate.

Update an existing Lean installation while preserving project requirements and records. Preview by default; apply only the plan the user approved. No commit or push, global settings change, or downgrade.

1. Read the installed `AGENTS.md`, `.lean/PROJECT.md` and `lean mode show`. Inventory pending work and active writers (open trackers, claims, running `lean spawn run` agents); stop affected writers through their owners before apply; never reset or auto-release claims.
2. Preview: `python3 .lean/bin/lean update preview [--ref <ref>] [--source <url>] [--workspace <dir>]`. It pins the highest stable semantic-version tag unless a ref is given, clones it into an external workspace (never inside a Git checkout), refuses an older release, and writes `plan.json` there. Nothing in the target changes. For a 4.x installation, which has no `lean` command yet, run the preview from the pinned v5 release instead: `python3 <release>/.lean/bin/lean update preview --target <project>`; only run code from a release the user chose to trust.
3. Read the plan with the user: files written (new, unmodified locally, or a major-version migration), conflicts (changed locally and upstream; kept unless `--take <path>`), files deleted (retired upstream and unmodified), files kept for review (retired but modified), merged files (`AGENTS.md`/`CLAUDE.md` take the upstream body and keep `## Project additions`; `.claude/settings.json` and `.codex/hooks.json` replace only Lean's hook entries and keep the project's own hooks, permissions and status line), and migration notes (4.x gate commands rewritten to `lean`, `.codex/quality-gate.json` moved to `.lean/gate.json`, retired skill links removed). Project-owned files (`PROJECT.md` outside its gate block, `config.json`, `models.json`, `gate.json`, `skill-effort.json`, trackers, queue) are never replaced. Grill material choices; accept the concrete plan through scope.
4. Apply exactly the approved plan: `python3 .lean/bin/lean update apply --workspace <dir> [--take <path> ...]`. It refuses when the target changed since preview, snapshots every touched path and journals each step. `lean update rollback --workspace <dir>` restores the snapshot while nothing changed after the update.
5. Run `lean lint`, `lean mode check`, the project's actual gate (`lean gate run`), HIGH independent review and `/lean-gate`. Control changes from an update need the covering HIGH review or recorded user approval (`lean gate accept-controls`). APPLIED means written, not DONE. Report changed and preserved files, the upstream commit, checks and review, limitations, and the rollback command.

Use delta context on retries: refresh changed revisions and conflicts rather than restarting. Stop when the preview report is complete or the approved update passes its checks and review; do not seek unrelated upgrades.
