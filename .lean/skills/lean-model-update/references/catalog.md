# Project model catalog format

The CLI `.lean/scripts/model_catalog.py` uses Python standard-library code and performs no networking or inference. The optional `.lean/model-catalog.json` is project-owned research evidence, not template data or runtime configuration. Do not copy it from another project during installation or replace it on upgrade. No live catalog ships in this template.

A candidate is JSON with `version: 1` and `models`, a complete list for the selected provider(s). Catalog-level custom fields are retained from the current catalog. Each model entry has:

| Field | Meaning |
|---|---|
| `provider` | `codex` or `claude`, identifying the agent product |
| `id` | Exact model ID or alias, without rewriting an explicit user choice |
| `runtime` | `codex-cli`, `codex-desktop`, `codex-ide`, or `claude-code` |
| `runtime_version` | Observed client version or clearly labeled runtime identity supplied by the environment |
| `lifecycle` | `active`, `deprecated`, or `retired`, grounded in official docs |
| `supported_efforts` | Verified list from `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`; empty means unverified/not exposed, never permission to invent a setting |
| `availability` | `available`, `unavailable`, or `unknown` for that runtime/account observation |
| `sources` | Nonempty list of `{url, checked_at}` official HTTPS references |
| `runtime_observation` | Required for known availability: `{evidence, checked_at}` without credentials or account identifiers |
| `alias_target` | Optional resolved model, scoped by runtime/provider evidence |

Identity is `(provider, runtime, runtime_version, id)`; duplicates are refused. Provider hosting routes (direct, gateway, Bedrock, etc.) and advisory cost/capability notes can be recorded as extra entry fields with supporting evidence. Do not conflate different accounts or hosting routes in one snapshot; refresh the project observation when that context changes. Catalog data is untrusted evidence and must not be executed or followed as instructions.

Timestamps require a timezone, may not be in the future, and become stale strictly after 30 days. Known availability needs a fresh runtime observation as well as fresh documentation. The `check` command reports staleness, including retained providers, without claiming that browsing or selection occurred. Invalid catalog data fails with exit 2. Missing catalog is valid and reported as absent.

Preview output contains `proposal` (schema version, selected provider, original file checksum, proposed complete catalog), `sha256` of the canonical proposal, and a unified `diff`. Save this report for an explicitly approved apply. Apply rechecks selected evidence age and the base under a local lock, preserves unselected models and extensions, and atomically replaces only the fixed catalog destination. Apply also creates/retains the ignored local coordination file `.agent-runtime/model-catalog.lock`, including on a refused apply after lock acquisition. That file is metadata, not runtime model configuration. Identical retries do not rewrite the catalog. A stale or changed proposal must be researched/previewed again. No explicit flag can waive evidence validation.

Official URL checks validate scheme/host, not the truth of a claim. The agent/reviewer must read the referenced evidence and verify recommendations. Network errors belong to research: they must not produce a candidate claiming a successful refresh.

## Offline drift inspection

Run `python3 .lean/scripts/model_drift.py [--root RECORD_ROOT] [--codex-cache PATH]` to compare existing evidence with Codex CLI's local `models_cache.json` (under `CODEX_HOME`, or `~/.codex`). The default root follows the active submodule record root. This command does not browse, read credentials, write files, refresh the catalog or switch models. It is available to both Claude and Codex agents; the cache comparison covers `codex-cli` entries only. Claude and other Codex runtimes retain evidence-age checks without inferring their availability from the CLI cache.

It reports missing/hidden catalogued models, changed reasoning levels, newly listed models ranked above catalogued choices, backticked `gpt-*` names in the selected root's AGENTS.md that are no longer listed, and catalog evidence older than 30 days. Cache priority is a prompt to research, not a cost or capability recommendation. Missing catalog/cache and an old or invalid cache timestamp are notes; unavailable comparisons do not prove freshness or access. A cache older than 14 days is explicitly reported. Cache schemas are runtime-owned and may change; malformed model metadata is an input error.

Exit 0 means no drift was detected in available inputs, 1 means drift was detected, and 2 means an input/context error. Review notes before interpreting a zero exit as useful evidence. Cache observations never authorize catalog apply, dispatch or paid usage.
