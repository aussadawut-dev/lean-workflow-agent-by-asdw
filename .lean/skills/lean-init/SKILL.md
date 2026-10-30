---
name: lean-init
description: Choose workflow mode and execution routing, then fill PROJECT.md from real repository facts.
user-invocable: true
argument-hint: "[standard|tracker|full] [--execution direct|delegated]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md`; keep model reasoning effort separate.

1. Read `AGENTS.md`, `.lean/PROJECT.md`, and `python3 .lean/bin/lean mode show`. Missing `.lean/config.json` means unconfigured `standard`/`direct`; do not fail merely because the file is absent.
2. Reuse any user-selected mode/execution, including explicit `$ARGUMENTS`. Otherwise, for initial setup ask the user to choose `standard` (session evidence), `tracker` (workset documents) or `full` (tracker plus claim queue). Explain that `direct` is the execution default and `delegated` enables Controller/worker routing; do not infer a heavier mode or delegation from project size. Do not ask again about an accepted choice.
3. Run `python3 .lean/bin/lean mode configure <mode>` and add `--execution delegated|direct` for an explicit execution change. Omission preserves execution. For an explicitly requested lower mode, run `lean mode downgrade <mode> --dry-run`, explain blockers and pending IDs, then `--apply` once blockers are resolved; include `--keep-pending` only when the user accepts pausing existing work. Do not auto-release leases, fabricate DONE, delete records or hand-edit config to bypass the guards.
4. Inspect root files, manifests, CI, top-level directories and existing READMEs. Fill PROJECT sections only with found facts; leave undefined conventions as such. List High-risk areas as bullets naming backticked repository paths or globs without spaces; the gate requires HIGH review for changes there. Then run `python3 .lean/bin/lean evidence high-risk --coverage` and, when it warns, narrow the areas before saving. Do not prescribe an application stack, install new dependencies or reuse credentials for discovery.
5. Run each safe, fast command once and note the result. Put deterministic checks between PROJECT's gate markers, one command per line; each command must preserve failures (for a formatter: `command -v gofmt >/dev/null && output=$(gofmt -l .) && test -z "$output"`). When the project's tests can be selected by impact, record that command for everyday runs and keep the full run for CI and releases (`.lean/policy/TESTING.md`). For Lean's own tests, a project that uses Lean puts `python3 .lean/bin/lean test --smoke` in its gate, not `--changed` or `--all`; Lean's CI runs its full suite. Empty gates block. If a controls baseline already exists, record this already approved onboarding change with `lean gate accept-controls --reason '<matching setup approval>'`; never record approval that was not given. Add one `<!-- trusted-control-refs: refs/remotes/origin/<default branch> -->` line below the gate block naming the upstream branches the project reviews and merges from.
6. Check `.lean/models.json` against the providers the user has (`lean models check --live`) and keep `max_agents` at 1 unless the user asks otherwise. Mention `lean watch` for a live progress pane.
7. Record actual documentation routes. Tracker/full mode creates tracking guides/templates; full also creates a queue guide. Preserve existing project documents and retain the workflow LICENSE/notice when importing into an existing project.
8. Run `python3 .lean/bin/lean mode check` and `lean lint`. Report chosen mode/execution, changed facts and remaining undefined fields. Do not create application tasks or queue items merely to initialize the workflow.

$ARGUMENTS
