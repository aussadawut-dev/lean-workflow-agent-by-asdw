---
name: lean-catalog
description: Propose refreshed Codex/Claude model metadata for the catalog; apply only an explicitly authorized proposal. Never switches session models or global runtime configuration.
user-invocable: true
argument-hint: "[codex|claude|all]"
---

# Lean Catalog

Input: `$ARGUMENTS`, or the current task when substitution is unavailable. Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity; this never changes model reasoning effort.

Read AGENTS, PROJECT and `workflow.py show` once; reuse accepted scope and valid context. Default to the active agent's provider; ask only if unknown. `all` selects both. Refresh requests authorize a proposal, not catalog apply or model switching.

For offline drift inspection only, run `python3 .lean/scripts/model_drift.py`; load [the offline reference](references/catalog.md#offline-drift-inspection) for inputs/limits/exit codes. This is not refresh evidence. Read [catalog format](references/catalog.md) when preparing a candidate, not unrelated runtime docs.

1. Research current official model/configuration, effort, lifecycle and subagent evidence for the selected provider/runtime. Reuse checked sources only while fresh, relevant and uncontradicted; do not fabricate a new check date. Inspect exposed choices/version: public API lists do not prove runtime/account access. No credential reads or paid probes. Unavailable browsing blocks claims of verified refresh.
2. Record URLs, actual dates, provider/runtime/version, exact IDs/aliases, efforts and lifecycle. Availability is `unknown` unless observed in that runtime. Preserve explicit choices and disclose alias changes/retirements; cost/capability advice needs sources, not name-based rankings. Grill material conflicts, unsupported effort, retirement or increased spend; metadata never authorizes billing/dispatch.
3. Prepare a complete replacement list for each selected provider, including retained runtime/version variants. Disclose removals and capability/alias changes. Evidence must be no more than 30 days old. Preserve unselected providers/extensions. Use a task-local candidate, never live runtime settings or a second tracker.
4. Run `python3 .lean/scripts/model_catalog.py preview --provider codex|claude|all --candidate PATH`. Show proposal, diff and `sha256`; preview writes nothing. Saving candidate/report evidence does not update the catalog.
5. Stop at proposal without explicit approval of that exact apply. Tooling implementation approval is insufficient. Once authorized, run `python3 .lean/scripts/model_catalog.py apply --proposal REPORT_PATH --sha256 APPROVED_DIGEST`. Reuse matching approval on unchanged retries; changed base/proposal needs fresh preview and affected-scope approval. Only the project catalog and ignored `.agent-runtime/model-catalog.lock` change, never session/global settings or reviewer definitions.
6. For changed files use `lean-task`, deterministic validation, required-depth `lean-review` over catalog diff/evidence and `lean-gate`. A digest binds content, not truth. Report stale/missing evidence. No automatic commit, push, merge or model switch.

Use delta context on retry: recheck changed entries, source freshness and proposal/base drift; preserve the complete selected-provider list. Stop when the requested proposal is complete or the approved apply is validated/reviewed, with remaining gaps explicit. Future dispatch still requires current runtime availability, accepted choices and MODELS policy; absent/stale catalogs are not onboarding blockers, and research alone never makes a model eligible or waives quality/premium/paid-usage rules.

$ARGUMENTS
