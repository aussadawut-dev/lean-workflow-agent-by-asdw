# Agent policy router

Lean Workflow Baseline 3.3.0. See `CHANGELOG.md` for changes and migration steps.

This directory contains operating rules and their self-checks. It is not application structure and prescribes no stack or primary provider. `AGENTS.md` is canonical; `CLAUDE.md` imports it. Shared procedures in `.claude/skills/` have Codex adapters in `.agents/skills/`.

## Setup and modes

Use `/lean-init` or `python3 .lean/scripts/workflow.py configure standard|tracker|full`. Add `--execution direct|delegated` for execution routing. `show` reads the settings, including a missing-file fallback; `check` validates mode and records. Missing configuration means unconfigured standard/direct, and onboarding prompts for a mode. Do not infer a heavier mode or discard accepted choices.

Explicit mode lowering uses `downgrade <lower-mode> --dry-run` and `--apply`; add `--keep-pending` only to acknowledge paused work. Active leases block every downgrade; active trackers also block standard. Preview keeps all files intact; apply preserves records/execution and locks/rechecks before updating config. See `policy/WORKFLOW.md`.

- `standard`: session contract, tests, validation, review and gate.
- `tracker`: standard plus one workset tracker per non-trivial task.
- `full`: tracker plus local lease-backed queue ownership.

Direct execution is the portable default; delegated execution uses the Controller/worker procedure. Repository mode, execution strategy, model choice and review depth are separate. Unix tools support macOS/Linux/WSL; native Windows is not supported. Claude hooks are provider-specific; Codex runs the gate explicitly.

Queue cleanup uses `/clean-queue old` (DONE older than 30 days) or `/clean-queue all` (all DONE). Preview/apply are available through `clean-queue old|all --dry-run|--apply`; original records move into project-owned queue history, not deletion. Trackers and unfinished items remain. Undated legacy DONE items are skipped by old. See `policy/WORKFLOW.md`.

Model research updates use `/lean-model-update codex|claude|all`. Preview is the default; explicitly approved apply updates an optional project-owned catalog and retains an ignored local catalog lock file. Session/global settings stay under runtime control. See `policy/MODELS.md`.

Use `/lean-compress` for concise, clear workflow prose. It inventories and fully reads all authorized workflow files before compression, preserves rules/protected content, previews by default and edits only approved targets.

## Layout and ownership

- `PROJECT.md` and `config.json`: project-owned facts, gate, mode and execution.
- `policy/`, shared skills and adapters: workflow-owned; upgrade together.
- `templates/`: generic record templates, not task history.
- `scripts/`, `tests/`: mode/lease tooling and workflow checks.
- `CUSTOMIZING.md`: current ownership and upgrade checklist.
- `LICENSE`: retain the workflow copyright/permission notice when importing.
- `CHANGELOG.md`: historical versions and migrations.

Mode setup creates project-owned tracking/queue guides; the distributable template contains no work records or leases. Preserve project additions and local extensions during upgrades.

## Read when needed

- Unfamiliar area or project commands -> `PROJECT.md`
- Setup, import or upgrade -> `CUSTOMIZING.md`, `/lean-init`, `config.json`
- Non-trivial planning, states, modes or claims -> `policy/WORKFLOW.md`
- Risk/quality/budget or result format -> `policy/CONTRACTS.md`
- Behavior change or bug fix -> `policy/TESTING.md`
- Quality floor and completion -> `policy/QUALITY.md`
- Medium/high review -> `policy/REVIEW.md`
- Model/effort/dispatch -> `policy/MODELS.md`
- Context expansion -> `policy/CONTEXT.md`
- Tool or delegation choice -> `policy/TOOLS.md`
- Failure or retry -> `policy/RECOVERY.md`

Start with the shallowest sufficient context. Do not load every policy or workflow internal by default. Trivial work still needs its contract/evidence but no formal tracker or scope spec.
