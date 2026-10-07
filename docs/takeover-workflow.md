# Taking over an existing agent workflow

Use a trusted Lean checkout to migrate another repository's workflow and document organization. The target's project rules, accepted decisions, unfinished work, permissions and history must remain accounted for.

```text
# Claude Code
/lean-takeover-workflow "/path/to/target"
/lean-takeover-workflow "/path/to/target" --preview

# Codex
$lean-takeover-workflow "/path/to/target" --preview
```

The default audits and prepares a concrete plan/diff, then applies after matching approval. Preview stops at the proposal and leaves the target intact. An accepted plan can be continued with `--apply <plan-id>` using its recorded external session. Missing approval or changed revisions require a new or refreshed proposal; a plan id alone is not consent.

## User decisions

Grill asks about material intent and tradeoffs, using evidence from the repository. Expect recommendations with alternatives and consequences: which old behavior to keep, how to resolve conflicts, which runtime capabilities still matter, and how ambiguous work records should migrate. Answers are reflected back and tied to the resulting operations and acceptance checks. There is no mandatory number of questions or rounds; accepted choices are reused and routine reversible mechanics proceed directly.

## Coverage and document ownership

The agent fully reads authorized workflow files and their local dependencies, including nested rules, skills/resources, public settings, hooks/scripts, workflow CI, tests, manifests and relevant project records. Fingerprints and search results do not count as a full read. Credentials, private settings, generated files and runtime internals are excluded with reasons. External references, symlinks and nested repositories require separate scope; a missing required read blocks its dependent migration.

Generic process maps to Lean procedures. Facts/commands/gate belong in target `.lean/PROJECT.md`; shared project rules belong in AGENTS Project additions; runtime rules remain with their runtime. Product specifications, architecture, ADRs and runbooks stay in project docs linked through documentation routes. Tracker/full uses `docs/tracking/`, and full uses `.agents/queue/`; existing valid records and configured choices are retained. Foreign records need explicit schema/status/ID mapping, not guessed owners or fabricated completion.

A private staging tree materializes the reviewed public workflow result before target writes. Run safe deterministic workflow checks there and record their results; staging excludes secrets/generated dependencies and does not substitute for the actual target gate.

The plan merges settings, gitignore, application gates/CI and project extensions, fixes active links/imports and removes competing workflow authority. It never imports source project facts, records, model settings, custom application agents/skills, credentials or project licenses. Original public workflow bytes are snapshotted outside the target, where old instruction filenames cannot remain active.

## Apply and recovery

The [shared procedure](../.lean/skills/lean-takeover-workflow/SKILL.md) owns interpretation and approval. Its [tool interface](../.lean/skills/lean-takeover-workflow/references/tooling.md) records inventory, decisions, rule mappings, exact writes and source/target fingerprints in a private session outside both repositories. Portable source files come from the release’s `.lean/assets.json` registry, so adjacent source project extensions are not copied. Keep the session path; it contains recovery data and must not be published.

Apply takes the local Lean queue lock and refuses live claims. Stop affected foreign workers separately; the lock cannot protect against unrelated editors. Each write has an original snapshot and intent/completion journal. Resume uses the same approved plan after interruption; rollback restores only the journal's files and refuses subsequent edits. Git reset, commit and push are not used. The coordination lock may remain after rollback.

APPLIED means the writer finished. DONE requires the target's actual Quality Gate, workflow/reference/permission/record checks and HIGH independent semantic review. Missing tools, unsupported conversions or pre-existing gate failures are reported with evidence. This command does not configure global skill discovery or migrate global runtime settings.
