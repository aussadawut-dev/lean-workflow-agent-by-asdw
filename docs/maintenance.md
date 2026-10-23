# Workflow maintenance

[Back to README](../README.md)

Run the CLI examples from the repository root. Enable the optional skill pack before using the skills here. The examples use Claude syntax; in Codex, use `$skill-name` with the same arguments.

## Keep the prose clear

Use `lean-compress` to remove repeated wording and filler while keeping the rules and practical meaning. Both runtimes use the [same procedure](../.lean/skills/lean-compress/SKILL.md). There is no fixed compression target.

```text
/lean-compress workflow --preview
/lean-compress README.md --preview
/lean-compress README.md --apply
```

Preview is the default. `workflow` selects editable workflow prose; explicit paths limit the files. `--apply` requests edits inside approved scope. Matching approval is reused. New scope or changes to workflow behavior need a decision before dependent edits. Reading a file alone does not authorize rewriting it.

Explicit paths read each target fully with applicable instructions, canonical rules and affected callers. Search for scripts, hooks or tests that consume the text; read relevant dependency sections and expand when needed to preserve meaning. Links do not require loading unrelated subtrees. Edits stay limited to named files.

`workflow` inventories authorized workflow paths, then fully reads selected editable prose and relevant canonical rules/consumers. It does not require reading every script or test. Keep a compact coverage record of edited revisions, rule sources, consumers, preservation checks and exclusions. Report unread/deferred areas; an explicitly requested exhaustive audit still needs full authorized coverage. Listings, snippets and hashes are not full reads. Missing required context blocks dependent edits; reread changed target revisions and reuse valid context on rework.

Exclude credentials, private settings, caches and runtime internals, and report those exclusions. Map each original rule to the proposed wording: actor, trigger, prerequisites, action, order, limits, exceptions, evidence and failure behavior.

Keep frontmatter, imports, headings/anchors, code/Mermaid, inline code, commands, links, paths, identifiers, numeric limits, versions, gate markers and license notices unchanged. Code, tests, configuration and project history provide context and stay outside prose compression. Preserve project additions and unrelated pending work.

Run preservation checks and the project gate before reviewing the actual diff. HIGH-risk areas need independent review; tests alone cannot establish preserved meaning. Report measured byte/word changes and unread/unchanged targets. Claim token savings only with measurement. Stop when selected prose is clear and required preservation, validation and review pass; further shortening needs a concrete benefit. The command does not publish or call a paid model API.

## Update installed Lean files

Use `/lean-update [--ref <tag|branch|commit>]` to preview an upgrade from the upstream stable tag. The [shared skill](../.lean/skills/lean-update/SKILL.md) pins the commit, checks exact changes, preserves project data and customizations, and uses external staging/snapshots for approved apply and recovery.

Older or incompatible releases block writes. Project-owned `.lean/upstream.json` keeps the source information. The procedure does not commit, push or change global configuration.

## Clean a repository

Use `/lean-prune repo` to audit clutter and obsolete source, tests, dependencies, docs, assets, config, scripts and workflow files (or `/lean-prune queue <old|all>` for completed queue items). Preview is the default for repository cleanup. The [skill](../.lean/skills/lean-prune/SKILL.md) shows exact removals/reference edits, evidence, impact and checks before applying with matching approval. A lack of references alone cannot establish that a file is unused. Uncertain and protected candidates stay in place.

The [helper](../.lean/scripts/clean_repo.py) inventories without writes and applies only a fingerprinted plan. It saves original bytes/modes in a private external recovery session, preserves Git's index, and blocks dirty/staged work, symlinks, nested repositories, protected state, drift and new descendants.

Untracked work stays unless explicitly proposed with verified regeneration evidence; ordinary Python cache and OS debris are recognized. Stop repository writers for apply/restore. Partial batches are journaled and recoverable. Restore refuses later edits. There is no automatic backup purge, commit or push.

`repo apply <plan-id>` uses the presented session; `repo restore <session-path>` performs guarded recovery. Keep the session path. See the [tool and proposal format](../.lean/skills/lean-prune/references/tooling.md). APPLIED still needs project checks and required review before DONE. Installing the skill does not authorize repository cleanup.
