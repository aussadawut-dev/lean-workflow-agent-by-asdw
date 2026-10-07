---
name: lean-compress
description: Shorten agent-workflow prose while preserving clarity, operational meaning and protected content. Read the complete workflow before proposing edits; preview by default, apply only within approved scope.
user-invocable: true
argument-hint: "[workflow|PATH...] [--preview|--apply]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

# Lean Compress

Make prose concise and easy to follow. Remove filler, repetition and needless indirection; keep complete, precise instructions. Do not use cryptic fragments, invented abbreviations or a target compression ratio. Shorter text is useful only when readers retain the same understanding and actions.

`/lean-compress workflow` targets editable workflow prose. `/lean-compress PATH...` limits edits to named prose files. `--preview` is the default and produces proposed changes without modifying targets. `--apply` requests writing the accepted compression scope; resolve new/material scope through `/lean-scope` first. Existing matching approval needs no repeat. Neither invocation authorizes publishing, paid inference, changing workflow behavior or editing runtime settings.

## Read the whole workflow first

Before proposing any compression, inventory and fully read every authorized workflow file, not just the target or search matches. Cover root AGENTS/CLAUDE/README/CONTRIBUTING and ownership/license guidance; all `.lean/` policies, project facts, public mode config, changelog, templates, scripts and tests; `.lean/skills/` shared skills/resources and `.lean/roles/` shared roles; `.claude/` runtime entrypoints, public settings and hooks; both runtimes' discovery links; and workflow CI/PR templates under `.github/`. Follow local workflow references to project extensions where authorized. Code and configuration are read for understanding, not for compression.

Include relevant tracked and untracked workflow files and preserve other pending work. Exclude `.git` internals, caches, generated dependencies, credentials, private/local settings, transcripts and runtime claims. Reading the whole workflow is not permission to read secrets or bypass access restrictions. Project task/history records are not compression targets; inspect only authorized records required to understand the accepted scope.

Record a coverage ledger with each path, content revision/hash, purpose and fully-read status, plus explicit exclusions and reasons. A directory listing, grep excerpt, file hash or summary is not a full read. Read large files in bounded, consecutive chunks through EOF; reopen truncated/missing chunks. Do not claim full coverage or begin compression while an in-scope file is unread/unavailable; report the gap and block dependent work. If content changes after the read, reread its complete changed revision before editing it. This exhaustive-read rule belongs to this skill's workflow audit; normal unrelated tasks retain their usual context routing.

## Preserve meaning and executable content

Build a before/after rule map for every target. Preserve each rule's actor, trigger, prerequisites, action, ordering, evidence, limits, exceptions, failure handling and authorization. In particular keep risk/quality floors, bounded review rounds, ownership/lease rules, model/billing gates, mode distinctions and project-owned additions. Do not turn MUST into MAY, remove negation, broaden permission or erase an exception.

Preserve byte-for-byte: YAML frontmatter, imports, headings/anchors, fenced and indented code (including Mermaid), inline code, commands, paths, links/URLs, identifiers, numeric limits, versions/dates, gate markers and license notices. Keep table layout, list hierarchy and procedure order. Treat ambiguous mixed prose/code regions as protected. History/evidence, code, tests and configuration stay unchanged unless a separate approved task authorizes that work.

Deduplicate only when the rule map proves equivalence and the surviving canonical rule remains reachable from every caller. Keep discovery-link integrity and shared authority. If compression would need a behavior change, moved/deleted anchor or new exception, stop that affected edit and use `/lean-grill` and `/lean-scope`; do not hide redesign inside shorter wording. Leave already concise text unchanged.

## Preview, validate and review

1. Read AGENTS and the policy router, determine mode/execution, then complete the coverage ledger. Use `/lean-task` for the accepted work; tracker/full records follow the existing workflow.
2. Show target paths, proposed before/after text or diff, the rule map and preserved regions. In preview, place proposals in the response or an isolated temporary workspace, never over the targets. Do not create permanent backup files or invent task records in the template.
3. Apply only an explicitly authorized matching scope. Check baseline revisions and protect unrelated edits. Use Git diff or temporary originals for comparison/recovery; if no recoverable baseline exists, establish one without overwriting the source before writing.
4. Verify protected regions against the original, check references/parity and run the actual PROJECT Quality Gate before semantic review. Validate diagram syntax if diagrams are changed by a separately approved task. Add meaningful tests for changed tooling; prose edits need preservation evidence rather than wording-matching tests. Never weaken checks to satisfy a size target.
5. Review the rule map and shipping diff at the deeper of risk and quality. HIGH-risk areas require an independent reviewer receiving the contract and diff without author reasoning. Follow the existing bounded review cycle; if meaning cannot be preserved, keep the affected original and report the limitation. A passing test suite alone does not establish semantic equivalence.
6. Run `/lean-gate` and report coverage, changed/unchanged targets, preservation results, validation and review scope. Report byte/word changes accurately; token savings require a named tokenizer and measurement, otherwise label them unmeasured. Do not claim improved quality or DONE solely because text is shorter.

Example: “In order to finish the task, make sure that every required check has passed.” becomes “Finish only after every required check passes.” A rule such as “After the second REWORK, allow one final pass, then report BLOCKED if it still fails” keeps its limit, ordering and failure outcome even if surrounding explanation is shortened.

$ARGUMENTS
