---
name: lean-init
description: Choose workflow mode and execution routing, then fill PROJECT.md from real repository facts.
---

1. Read `AGENTS.md`, `.lean/PROJECT.md`, and `python3 .lean/scripts/workflow.py show`. Missing `.lean/config.json` means unconfigured `standard`/`direct`; do not fail merely because the file is absent.
2. Reuse any user-selected mode/execution, including explicit `$ARGUMENTS`. Otherwise, for initial setup ask the user to choose `standard` (session evidence), `tracker` (workset documents) or `full` (tracker plus claim queue). Explain that `direct` is the execution default and `delegated` enables Controller/worker routing; do not infer a heavier mode or delegation from project size. No need to ask again about an accepted choice.
3. Run `python3 .lean/scripts/workflow.py configure <mode>` and add `--execution delegated` or `--execution direct` for an explicit execution change. Omission preserves execution. Mode upgrades preserve and validate documents. For an explicitly requested lower mode, run `downgrade <mode> --dry-run`, explain blockers/pending IDs, then use `--apply` once blockers are resolved; include `--keep-pending` only when the user accepts pausing existing work. Active claims block all downgrades, and active trackers block standard. Do not auto-release leases, fabricate DONE, delete records or hand-edit config to bypass the guards. Execution changes remain a separate configure step.
4. Inspect root files, manifests, CI, top-level directories and existing READMEs. Fill PROJECT sections only with found facts; leave undefined conventions as such. Do not prescribe an application stack, install new dependencies or reuse credentials for discovery.
5. Run each safe/fast command once and note the result. Put deterministic checks between PROJECT's gate markers, one command per line. Each command must preserve failures. For a formatter, use `command -v gofmt >/dev/null && output=$(gofmt -l .) && test -z "$output"` rather than relying only on printed output or masking a missing tool in a substitution. Verify the selected command.
6. Record actual documentation routes. Tracker/full mode creates tracking support guides/templates; full also creates a queue guide. Preserve existing project documents and retain the workflow LICENSE/notice when importing into an existing project.
7. Run `python3 .lean/scripts/workflow.py check`. Report chosen mode/execution, changed facts and remaining undefined fields. Do not create application tasks or queue items merely to initialize the workflow.

$ARGUMENTS
