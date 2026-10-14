# Workflow maintenance

[Back to README](../README.md)

Run CLI examples from the repository root.

## Keep workflow prose lean and clear

Enable the optional maintenance pack before invoking `/lean-compress` to remove repetition and filler while preserving the same rules and practical meaning. The [shared procedure](../.lean/skills/lean-compress/SKILL.md) works for Claude and Codex from the same source. It uses clear, concise language and has no fixed compression ratio.

```text
/lean-compress workflow --preview
/lean-compress README.md --preview
/lean-compress README.md --apply
```

Preview is the default. `workflow` targets editable workflow prose; paths restrict which prose files may change. `--apply` requests changes within an approved scope. A matching approval is reused; a new scope or change to workflow behavior needs resolution before dependent edits. Reading a file never authorizes rewriting it.

**Read every corner of the workflow before compressing.** Inventory and fully read the canonical contract, router/policies, project facts, all skills/resources/discovery links, reviewer, hooks/settings, scripts/tests/templates, CI, README and history/ownership guidance. Record each file and revision in a coverage ledger. Large files must be read through EOF in chunks; listings, grep snippets, hashes and summaries do not establish coverage. An unread or inaccessible in-scope file blocks dependent compression. Exclude credentials, private settings, caches and runtime internals; report exclusions rather than claiming they were reviewed.

Then map the original rules to the proposed wording: actor, trigger, prerequisites, action, ordering, limits, exceptions, evidence and failure behavior. Keep frontmatter, imports, headings/anchors, code/Mermaid, inline code, commands, links, paths, identifiers, numeric limits, versions, gate markers and license notices unchanged. Code, tests, configuration and project history are read for context and stay outside prose compression. Preserve accepted project additions and unrelated pending edits.

Run preservation checks and the project Quality Gate, then review the actual diff at the required depth. Independent review is required for HIGH-risk areas; tests alone cannot prove preserved meaning. Report measured byte/word changes and any unread/unchanged targets. Do not claim token savings without measurement. This complete-read requirement applies to the compression audit, rather than changing context routing for ordinary tasks. The command does not publish changes or call a paid model API.

## Repository cleanup

With the optional maintenance pack enabled, use `/lean-update-workflow [--ref <tag|branch|commit>]` to preview an upgrade from the Lean upstream stable tag. The [shared skill](../.lean/skills/lean-update-workflow/SKILL.md) pins the commit, preserves project data/customizations, reconciles exact changes and uses external staging/snapshots for approved apply and recovery. Older or incompatible releases block writes. Project-owned `.lean/upstream.json` retains provenance; no commit, push or global configuration change is implied.

Use `/lean-clean-repo` to audit clutter and obsolete source, tests, dependencies, docs, assets, configuration, scripts and workflow files. Preview is the default. The [shared skill](../.lean/skills/lean-clean-repo/SKILL.md) presents exact removals/reference edits, evidence, impact and checks before matching approval. Missing references alone do not prove a file is unused. Protected and uncertain candidates remain.

The [helper](../.lean/scripts/clean_repo.py) inventories without writes and applies only a fingerprinted plan, retaining original bytes/modes in a private external recovery session. It preserves Git's index, blocks dirty/staged work, symlinks, nested repositories and protected state, and rejects drift/new descendants. Untracked work is preserved unless explicitly proposed with verified regeneration evidence (ordinary Python cache/OS debris is recognized). Apply/restore require repository writers stopped; a partial batch is journaled and recoverable. Restore refuses later edits. No automatic backup purge, commit or push occurs.

`apply <plan-id>` uses the previously presented session; `restore <session-path>` performs guarded recovery. See [tooling and proposal format](../.lean/skills/lean-clean-repo/references/tooling.md). APPLIED still requires the project's checks and required review. Creating/installing this skill does not authorize cleaning any repository.
