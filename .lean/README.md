# Agent policy router

Lean Workflow Baseline 5.5.0. See `CHANGELOG.md` for changes and migration steps.

Operating rules, not application structure; no stack or primary provider is prescribed. `AGENTS.md` is canonical and `CLAUDE.md` imports it. `python3 .lean/bin/lean` runs every workflow tool (code in `.lean/lean/`). Procedures live in `.lean/skills/`; `.claude/skills/` and `.agents/skills/` hold discovery links.

## Setup and modes

Use `/lean-init` or `lean mode configure standard|tracker|full` (add `--execution direct|delegated`); `lean mode show` reads, `lean mode check` validates. Missing configuration means unconfigured standard/direct; never discard accepted choices. Downgrades, leases and records: `policy/WORKFLOW.md`.

- `standard`: session contract, tests, validation, review and gate.
- `tracker`: standard plus one workset tracker per non-trivial task.
- `full`: tracker plus local lease-backed queue ownership.

Direct execution is the default; delegated uses the Controller/worker procedure. Mode, execution, model, quality floor and review depth are separate. Supports macOS/Linux/WSL, not native Windows.

## Ownership

Project-owned: `PROJECT.md`, `config.json`, `models.json`, optional `gate.json` and `skill-effort.json`. Workflow-owned, upgraded together by `/lean-update`: `bin/`, `lean/`, `policy/`, `roles/`, `skills/` (and links), `templates/`, `tests/`, `evals/`. Upgrades preserve project additions and local extensions (`CUSTOMIZING.md`); retain `LICENSE`.

## Read when needed

- Unfamiliar area or project commands -> `PROJECT.md`
- Setup, import or upgrade -> `CUSTOMIZING.md`, `/lean-init`, `/lean-update`
- Non-trivial planning, phases, progress, modes or claims -> `policy/WORKFLOW.md`
- Risk/quality/budget or result format -> `policy/CONTRACTS.md`
- Behavior change, bug fix or which tests to run -> `policy/TESTING.md`
- Quality floor and completion -> `policy/QUALITY.md`
- Medium/high review -> `policy/REVIEW.md`
- Model list, spawning and effort -> `policy/MODELS.md`
- Context expansion -> `policy/CONTEXT.md`
- Tool choice -> `policy/TOOLS.md`
- Failure or retry -> `policy/RECOVERY.md`

Do not load every policy by default. Trivial work needs its contract and evidence but no tracker or scope spec. Context selection (`policy/CONTEXT.md`) never skips tests, review or gate checks.

## Procedure intensity

`/lean-effort [standard|high|ultra|reset] [lean-skill-name]` inspects (no arguments, read-only) or saves shared procedure intensity; missing means standard (`policy/SKILL-EFFORT.md`). All Lean procedures are user-invocable.
