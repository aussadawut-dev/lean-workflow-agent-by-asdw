---
name: lean-model-update
description: Research and propose refreshed Codex/Claude model metadata for the project catalog, applying only an explicitly authorized proposal. Does not switch session models or global runtime configuration.
user-invocable: true
argument-hint: "[codex|claude|all]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

# Lean Model Update

Read AGENTS, PROJECT and `workflow.py show`. Use the accepted scope; `/lean-scope` drafts new scope only if none matches. Default provider is the active agent's provider; ask if that cannot be determined. `/lean-model-update all` covers both providers. A request to refresh produces a proposal, not permission to apply it or switch a model.

1. Use `/lean-research` to check current official model, configuration, effort, lifecycle and subagent documentation. Inspect only the relevant runtime's exposed choices and version. Public API model lists do not prove Codex/Claude Code account access. No paid inference probes or credential reads are needed. If browsing is unavailable, report that refresh could not be verified; never fabricate success or current timestamps.
2. Read [catalog format](references/catalog.md) when preparing evidence. Keep source URLs and actual check dates, runtime/provider/version, exact model or alias, supported efforts and lifecycle. Mark availability `unknown` unless observed in the relevant runtime. Retain explicit user choices and record alias target changes; do not silently replace retired models. Research judgments about cost/capability are advisory and need sources, not inferred rankings from model names.
3. Use `/lean-grill` for material uncertainty: conflicting sources, alias/provider differences, unsupported effort, explicit choice conflicts, retirement or increased spend. Routine verified metadata changes within accepted scope need no repeated scope approval. Catalog evidence never grants billing or dispatch permission.
4. Prepare a complete replacement list for each selected provider (including all runtime/version variants to retain). Never silently omit existing entries: the preview diff must disclose removals, aliases and capability changes. Selected evidence must be no more than 30 days old. Preserve unselected providers and project extensions. Use a task-local candidate file, not live runtime settings.
5. Run `python3 .lean/scripts/model_catalog.py preview --provider codex|claude|all --candidate PATH` and show its proposal, diff and `sha256`. Preview itself writes nothing; saving candidate/report files is task evidence and does not update the catalog. In tracker/full, use the owning workset, not a second research tracker.
6. Stop at proposal unless applying that exact proposal is explicitly authorized. Approval of implementing this tooling is not catalog-apply authorization. After authorization, run `python3 .lean/scripts/model_catalog.py apply --proposal REPORT_PATH --sha256 APPROVED_DIGEST`. Reuse authorization for unchanged retries; a changed proposal or base requires a fresh preview and affected-scope approval. This updates only the project-local catalog and creates/retains an ignored `.agent-runtime/model-catalog.lock` for coordination, never session/global settings or the shared reviewer definition.
7. Follow `/lean-task`, `/lean-review` and `/lean-gate` for changed files: deterministic checks precede semantic review; review the shipping catalog diff and evidence at required depth. Report missing/stale evidence honestly. A digest binds proposal content but does not authenticate research claims. No automatic commit, push, merge or model switch.

For future dispatch, consult the catalog only alongside current runtime availability, accepted choices and MODELS policy. If absent or stale, keep normal runtime inspection/default behavior; catalog absence is not an onboarding blocker. Unverified models are not eligible merely because they appear in research. Model selection never bypasses quality, premium evidence or additional-paid-usage authorization.

$ARGUMENTS
