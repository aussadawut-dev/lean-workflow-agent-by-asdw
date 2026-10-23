---
name: lean-compress
description: Shorten agent-workflow prose while preserving meaning and protected content; preview by default, apply only within approved scope.
user-invocable: true
argument-hint: "[workflow|PATH...] [--preview|--apply]"
---

# Lean Compress

Input: `$ARGUMENTS`, or the current task when substitution is unavailable. Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity; keep model reasoning effort separate.

Shorten workflow prose without losing meaning. Use plain complete instructions, not cryptic fragments, invented abbreviations or a target compression ratio. Leave concise text unchanged.

`/lean-compress workflow` selects workflow prose; `/lean-compress PATH...` selects named prose files. `--preview` is the default and leaves targets untouched. `--apply` requests the accepted compression scope; resolve new/material scope through `/lean-scope`, reusing matching approval. Neither form authorizes workflow behavior changes, runtime settings, publishing or paid inference.

## Read what the target needs

`/lean-compress PATH...`: fully read each target, applicable AGENTS and the policy router. Trace each changed rule to its canonical definition and affected callers; search for references and scripts, hooks and tests that parse/check the text. Read relevant dependency sections, expanding to complete files when interpretation requires it. A link alone does not require loading its entire subtree. If a rule cannot be understood within this context, expand along its dependencies and explain why; edits stay limited to the named paths.

`/lean-compress workflow`: inventory authorized workflow paths, then select editable prose and read those targets fully. This is not a full read of every script or test. Inspect executable/configuration consumers and canonical rules where they affect meaning or preservation. Account for root entrypoints/guides, `.lean/` policies/skills/roles/templates, runtime discovery/settings/hooks and workflow CI; follow relevant project extensions. Report excluded, unread and deferred areas rather than claim a whole-workflow audit from partial inspection. Explicit requests for an exhaustive audit still require full authorized coverage.

For either scope include relevant tracked/untracked files and preserve pending work. Exclude `.git` internals, credentials, private settings, transcripts, caches, generated dependencies and runtime claims. Project history/task records are not compression targets; inspect only authorized dependencies. Inventory never grants secret access.

Keep a compact coverage record in the existing session/tracker: edited paths and revision/hash, canonical rule sources, affected consumers, preservation checks and exclusions/gaps. Listings, hashes and excerpts are not full reads. Read target files through EOF in bounded chunks, reopening truncated output. Block edits whose required context is unread/unavailable; on drift read the complete changed revision before editing. Use delta context on rework, retaining still-valid reads and decisions rather than restarting inventory and all procedures.

## Preserve meaning and executable content

Build a before/after rule map per target: actor, trigger, prerequisites, action/order, evidence, limits, exceptions, failure handling and authorization. Keep risk/quality floors, bounded review, ownership/leases, model/billing gates, modes and project additions. Never weaken obligations, negate a rule or broaden authority.

Preserve byte-for-byte: YAML frontmatter, imports, headings/anchors, fenced/indented code (including Mermaid), inline code, commands, paths, links/URLs, identifiers, numeric limits, versions/dates, gate markers and licenses. Keep table/list structure and procedure order; ambiguous mixed code/prose stays protected. History/evidence, code, tests and configuration need separate authorization to change.

Deduplicate only when equivalence is established and every affected caller can still reach the canonical rule. Preserve discovery links and shared authority. Behavior changes, anchor moves/deletions or new exceptions require separate scope/Grill; do not hide them in compression.

## Preview, validate and review

1. Use `lean-task` with the accepted scope and configured mode/execution; retain its owning records. Show target diff, rule map, protected regions and coverage gaps. Preview stays in conversation or an isolated temporary workspace; no permanent backup files or invented task records.
2. Apply only explicitly authorized matching scope after checking baseline revisions. Preserve unrelated work; establish recoverable originals before writing if Git/temporary originals cannot supply them.
3. Verify protected bytes, references and provider parity. Run the actual PROJECT Quality Gate before semantic review; meaningful tests cover changed tooling, while prose needs preservation evidence. Separately authorized diagram changes need syntax checks. Never weaken checks for size.
4. Review rule map and shipping diff at required risk/quality depth, independently for HIGH. Follow bounded review rounds; retain original text if equivalence cannot be established. Passing tests alone do not prove semantic preservation.
5. Use `lean-gate`, reusing current deterministic evidence. Report changed/unchanged paths, coverage, preservation, validation/review and gaps. Measure bytes/words; token savings require a named tokenizer and measurement, otherwise say unmeasured.

Stop when selected prose is clear, rule/protected-content checks pass and required validation/review is complete, or a specific gap blocks dependent edits. Do not pursue further shortening without a concrete benefit.

$ARGUMENTS
