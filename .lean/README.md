# Agent policy router

Lean Workflow Baseline 5.0.0. See `CHANGELOG.md` for changes and migration steps.

Operating rules and their self-checks; not application structure, and no stack or primary provider is prescribed. `AGENTS.md` is canonical and `CLAUDE.md` imports it. One command line, `python3 .lean/bin/lean`, runs every workflow tool; its code lives in `.lean/lean/`. Procedures live in `.lean/skills/`; `.claude/skills/` and `.agents/skills/` hold their discovery links.

## Setup and modes

Use `/lean-init` or `lean mode configure standard|tracker|full` (add `--execution direct|delegated`); `lean mode show` reads settings, `lean mode check` validates mode and records. Missing configuration means unconfigured standard/direct; do not infer a heavier mode or discard accepted choices. Downgrades, leases and records: `policy/WORKFLOW.md`.

- `standard`: session contract, tests, validation, review and gate.
- `tracker`: standard plus one workset tracker per non-trivial task.
- `full`: tracker plus local lease-backed queue ownership.

Direct execution is the portable default; delegated uses the Controller/worker procedure. Mode, execution, model choice, quality floor and review depth are separate. Unix tools support macOS/Linux/WSL, not native Windows. Claude and Codex run hooks; agy runs the gate explicitly.

## Ownership

Project-owned: `PROJECT.md`, `config.json`, `models.json`, optional `gate.json` and `skill-effort.json`. Workflow-owned, upgraded together by `/lean-update`: `bin/`, `lean/`, `policy/`, `roles/`, `skills/` and their discovery links, `templates/`, `tests/`. Preserve project additions and local extensions on upgrade (`CUSTOMIZING.md`); retain `LICENSE`.

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

Do not load every policy or workflow internal by default. Trivial work still needs its contract/evidence but no formal tracker or scope spec. `policy/CONTEXT.md` selects context by affected behavior; selection never skips tests, review or gate checks.

## Procedure intensity

`/lean-effort [standard|high|ultra|reset] [lean-skill-name]` inspects (no arguments, read-only) or explicitly saves shared procedure intensity; missing settings mean standard. `policy/SKILL-EFFORT.md` defines precedence and boundaries. All Lean procedures are user-invocable.
