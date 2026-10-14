# Taking over an existing agent workflow

[Back to README](../README.md)

Use a trusted Lean checkout to migrate another repository's workflow and document organization. Keep the target's rules, accepted decisions, unfinished work, permissions and history accounted for. Enable the optional pack first.

```text
# Claude Code
/lean-takeover-workflow "/path/to/target"
/lean-takeover-workflow "/path/to/target" --preview

# Codex
$lean-takeover-workflow "/path/to/target" --preview
```

The default audits the target and prepares a concrete plan/diff, then applies after matching approval. `--preview` stops at the proposal and leaves the target intact. Continue an accepted plan with `--apply <plan-id>` using its external session. Missing approval or changed revisions need a new or refreshed proposal. A plan ID alone is not approval.

## Decisions to settle

Grill works through important intent and tradeoffs using repository evidence: which old behavior to keep, how to resolve conflicts, which runtime features still matter, and how to map unclear work records.

Expect recommendations with alternatives and consequences. Answers are tied to operations and acceptance checks. There is no fixed question count. Accepted choices carry forward, and routine reversible steps can proceed.

## Read coverage and document ownership

The agent fully reads authorized workflow files and local dependencies, including nested rules, skills/resources, public settings, hooks/scripts, workflow CI, tests, manifests and relevant records. Fingerprints and search results cannot substitute for a full read.

Credentials, private settings, generated files and runtime internals are excluded with reasons. External references, symlinks and nested repositories need separate scope. A missing required read blocks the migration that depends on it.

Generic process belongs in Lean procedures. Facts, commands and gate go in target `.lean/PROJECT.md`; shared project rules go in AGENTS Project additions. Runtime rules stay with their runtime. Product specs, architecture, ADRs and runbooks stay in project docs linked through documentation routes.

Tracker/full uses `docs/tracking/`; full also uses `.agents/queue/`. Keep valid existing records and configured choices. Foreign records need explicit schema/status/ID mapping. Owners and completion evidence must not be invented.

A private staging tree shows the reviewed public workflow result before target writes. Run safe deterministic workflow checks there and record the results. Staging excludes secrets/generated dependencies and still needs the actual target gate afterward.

The plan merges settings, gitignore, application gates/CI and project extensions, fixes active links/imports and removes competing workflow authority. It leaves source project facts, records, model settings, custom application agents/skills, credentials and licenses out of the import. Original public workflow bytes are snapshotted outside the target so old instruction files cannot remain active.

## Apply and recovery

The [shared procedure](../.lean/skills/lean-takeover-workflow/SKILL.md) owns interpretation and approval. Its [tool interface](../.lean/skills/lean-takeover-workflow/references/tooling.md) records inventory, decisions, rule mappings, exact writes and source/target fingerprints in a private session outside both repositories.

Portable source files come from `.lean/assets.json`, so nearby source-project extensions are excluded. Keep the private session path for recovery and do not publish it.

Apply takes the local Lean queue lock and refuses live claims. Stop affected foreign workers separately; the lock cannot protect against unrelated editors. Every write has an original snapshot and intent/completion journal.

Resume uses the same approved plan after interruption. Rollback restores only journaled files and refuses subsequent edits. No Git reset, commit or push is used. The coordination lock may remain after rollback.

APPLIED means the writer finished. DONE still needs the target's actual Quality Gate, workflow/reference/permission/record checks and HIGH independent semantic review. Report missing tools, unsupported conversions or pre-existing gate failures with evidence. Global skill discovery and runtime settings are outside this migration.
