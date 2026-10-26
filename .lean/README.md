# Agent policy router

Lean Workflow Baseline 4.17.1. See `CHANGELOG.md` for changes and migration steps.

Operating rules and their self-checks; not application structure, and no stack or primary provider is prescribed. `AGENTS.md` is canonical and `CLAUDE.md` imports it. Procedures live in `.lean/skills/`; `.claude/skills/` and `.agents/skills/` hold the core discovery symlinks and any enabled extras.

## Setup and modes

Use `/lean-init` or `python3 .lean/scripts/workflow.py configure standard|tracker|full` (add `--execution direct|delegated`); `show` reads settings, `check` validates mode and records. Missing configuration means unconfigured standard/direct; do not infer a heavier mode or discard accepted choices. Downgrades, leases and records: `policy/WORKFLOW.md`.

- `standard`: session contract, tests, validation, review and gate.
- `tracker`: standard plus one workset tracker per non-trivial task.
- `full`: tracker plus local lease-backed queue ownership.

Direct execution is the portable default; delegated uses the Controller/worker procedure. Mode, execution, model choice, quality floor and review depth are separate. Unix tools support macOS/Linux/WSL, not native Windows. Claude hooks are provider-specific; Codex runs the gate explicitly or through its trusted lifecycle adapter.

## Optional skills and ownership

Nine core skills are discovered by default; `python3 .lean/scripts/skill_pack.py enable` adds the nine optional ones (`status`/`disable` inspect or reverse; reload runtime skills after). Details: `OPTIONAL.md`.

Project-owned: `PROJECT.md`, `config.json`, optional `skill-effort.json`. Workflow-owned, upgraded together: `policy/`, shared skills and discovery links, `templates/`, `scripts/`, `tests/`. Preserve project additions and local extensions on upgrade (`CUSTOMIZING.md`); retain `LICENSE`.

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

Do not load every policy or workflow internal by default. Trivial work still needs its contract/evidence but no formal tracker or scope spec. `policy/CONTEXT.md` selects context by affected behavior; selection never skips tests, review or gate checks.

## Procedure intensity

`/lean-effort [standard|high|ultra|reset] [lean-skill-name]` inspects (no arguments, read-only) or explicitly saves shared procedure intensity; missing settings mean standard. `policy/SKILL-EFFORT.md` defines precedence, record-root settings and boundaries. All discovered Lean procedures are user-invocable; optional discovery stays opt-in.
