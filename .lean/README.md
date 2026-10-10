# Agent policy router

Lean Workflow Baseline 4.1.0. See `CHANGELOG.md` for changes and migration steps.

This directory contains operating rules and their self-checks. It is not application structure and prescribes no stack or primary provider. `AGENTS.md` is canonical; `CLAUDE.md` imports it. Shared procedures live in `.lean/skills/`; `.claude/skills/` and `.agents/skills/` contain core discovery symlinks and any explicitly enabled extras.

## Setup and modes

Use `/lean-init` or `python3 .lean/scripts/workflow.py configure standard|tracker|full`. Add `--execution direct|delegated` for execution routing. `show` reads the settings, including a missing-file fallback; `check` validates mode and records. Missing configuration means unconfigured standard/direct, and onboarding prompts for a mode. Do not infer a heavier mode or discard accepted choices.

Explicit mode lowering uses `downgrade <lower-mode> --dry-run` and `--apply`; add `--keep-pending` only to acknowledge paused work. Active leases block every downgrade; active trackers also block standard. Preview keeps all files intact; apply preserves records/execution and locks/rechecks before updating config. See `policy/WORKFLOW.md`.

- `standard`: session contract, tests, validation, review and gate.
- `tracker`: standard plus one workset tracker per non-trivial task.
- `full`: tracker plus local lease-backed queue ownership.

Direct execution is the portable default; delegated execution uses the Controller/worker procedure. Repository mode, execution strategy, model choice and review depth are separate. Unix tools support macOS/Linux/WSL; native Windows is not supported. Claude hooks are provider-specific; Codex runs the gate explicitly.

## Optional maintenance

Nine core skills are discovered by default. Enable the seven maintenance skills with `python3 .lean/scripts/skill_pack.py enable` (`status` / `disable` inspect or reverse discovery). Read `OPTIONAL.md` for queue cleanup, model refresh, compression, repository cleanup, takeover, submodules and upgrades. Canonical tools/resources stay bundled; discovery changes never discard records or recovery capabilities. Reload runtime skills after toggling.

## Layout and ownership

- `PROJECT.md`, `config.json` and optional `skill-effort.json`: project-owned facts, gate, mode, execution and procedure preferences.
- `policy/`, shared skills and discovery links: workflow-owned; upgrade together.
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

## Procedure intensity

Use `/lean-skill-effort [standard|high|ultra|reset] [lean-skill-name]` to inspect or explicitly save shared procedure intensity. No arguments is read-only. Missing settings mean standard. `.lean/policy/SKILL-EFFORT.md` defines precedence and boundaries. Settings follow the active target record root; `--root` overrides it. All discovered Lean procedures are user-invocable; optional discovery remains opt-in.
