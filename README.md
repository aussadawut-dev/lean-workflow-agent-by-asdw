# Lean Workflow Agent by ASDW

A GitHub repository template for Claude, Codex and other coding agents. It supplies a shared task contract, meaningful tests, risk-based review and evidence before completion. It does not prescribe an application language, framework, architecture or primary agent.

## Start

Choose **Use this template** on GitHub, or copy without repository history:

```sh
npx degit aussadawut-dev/lean-workflow-agent-by-asdw my-project
cd my-project
git init
```

Open the project with your coding agent and run `/lean-init`. Codex uses the adapters under `.agents/skills/`; Claude uses the shared procedures under `.claude/skills/`. If slash-command discovery is unavailable, ask the agent to read the corresponding `SKILL.md` and follow it. Shared rules live in `AGENTS.md`; `CLAUDE.md` imports them.

Choose the workflow you need:

| Repository mode | What it adds |
|---|---|
| `standard` | Contract, validation, review and Quality Gate; evidence in the session. |
| `tracker` | Standard plus one workset document per non-trivial task. |
| `full` | Tracker plus queue items and local lease claims. |

The template starts with unconfigured `standard` mode and `direct` execution. Setup asks for a mode; an explicitly supplied choice is reused. Execution is separate: `direct` keeps implementation with the active agent; `delegated` makes it the Controller and sends bounded work to one worker. Parallel workers require explicit user intent and independent file ownership. Quality and review depth stay the same in every mode.

You can configure without an agent:

```sh
python3 .lean/scripts/workflow.py configure standard
python3 .lean/scripts/workflow.py configure tracker --execution delegated
python3 .lean/scripts/workflow.py show
python3 .lean/scripts/workflow.py check
```

Mode upgrades preserve records. A downgrade is refused until existing work and claims have a separately agreed migration. No queue items, task history or project-specific records ship with the template. Support guides/templates are created only when their mode is enabled.

## Procedures

Every procedure has a Claude skill and a thin Codex adapter; the procedure body has one owner.

| Skill | Purpose |
|---|---|
| `/lean-init` | Select mode/execution and discover real project commands. |
| `/lean-scope` | Reuse approved scope or resolve a new/expanded scope before work. |
| `/lean-research` | Compare alternatives with traceable evidence. |
| `/lean-grill` | Resolve material decisions and high-risk boundaries. |
| `/lean-task` | Contract, accepted scope, work, tests, validation and review. |
| `/lean-review` | Review the shipping delta at the required depth. |
| `/lean-gate` | Verify completion evidence and report the result. |
| `/lean-multi-agent` | Worker ownership, dispatch, claims and handoff. |

The active agent is the Controller unless the project chooses a different owner. Model choice follows the least costly capable model and supported effort available in the runtime. Premium dispatch needs concrete evidence that a cheaper option cannot satisfy the task. HIGH-depth independent review is mandatory even when implementation is direct. No model names, plan assumptions or volatile prices are pinned in portable policy.

## Runtime support

The tools use Bash, Git and Python 3.9+ standard libraries. Lease locking uses Unix `fcntl`: supported environments are macOS, Linux and WSL. Native Windows is not supported. Install ShellCheck to run the workflow self-check gate; CI uses Ubuntu with Python 3. No application dependencies or paid services are required.

Claude's `.claude/settings.json` wires SessionStart and Stop hooks. Stop runs the commands in `.lean/PROJECT.md`; Codex runs these commands explicitly through the shared procedures. Claude settings and permission denies are not a Codex hook or security configuration. Local lease tokens coordinate workers in one checkout; they are not a security boundary.

For headless Claude, the workspace must be trusted for settings permissions: open it interactively once or supply the tools permitted by your runtime explicitly. Keep secrets out of repository/tracker/dispatch records.

## Layout

```text
AGENTS.md                  Shared canonical contract and project additions
CLAUDE.md                  Claude entrypoint importing the shared contract
.lean/
  PROJECT.md               Project-owned facts, commands and Quality Gate
  config.json              Project-owned mode/execution choice
  README.md                Policy router
  CUSTOMIZING.md           Ownership, import and upgrade guidance
  LICENSE                  Workflow notice retained in existing projects
  CHANGELOG.md             Version history and migration steps
  policy/                  Portable rules
  templates/               Generic tracker and queue templates
  scripts/                 Mode/lease tooling and structural checks
  tests/                   Workflow regression and behavior checks
.claude/                   Shared skills, Claude hooks/settings/reviewer
.agents/skills/            Eight Codex adapters
.github/                   Workflow CI and PR Result Contract template
```

Fill `.lean/PROJECT.md` with actual project facts and checks. Keep undefined conventions undefined until work establishes them. Put project overrides below `## Project additions` in `AGENTS.md`; keep runtime-specific additions in `CLAUDE.md`. See [.lean/CUSTOMIZING.md](.lean/CUSTOMIZING.md) before importing or upgrading.

## Checks

```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-hooks.sh
python3 .lean/scripts/workflow.py check
python3 -m unittest discover -s .lean/tests -p 'test_*.py'
```

Tests exercise hooks, initial setup, all three modes, lease ownership, completion evidence/dependencies, FAILED status, duplicate tracker IDs, canonical review routing and adapter parity/links. Smoke tests also run after downstream setup with a separate project license and existing work records; they do not reset the host project. Structure checks exclude ignored dependencies and handle whitespace in paths. CI runs workflow checks when their files change; it does not imply that a downstream application's full gate is executed in CI. Add application checks separately.

## Importing into an existing project

Merge entrypoints/settings/gitignore/CI rather than replacing project content. Keep project ownership, accepted scope, configuration, commands, records, agents and skills. The generic templates and tooling are reusable; existing queue items, trackers, leases, caches, credentials and product files are not template material. Retain `.lean/LICENSE` for the copied workflow alongside your own project license.

This README and CONTRIBUTING describe the template and can be replaced in a downstream project. Workflow self-tests and CI may be removed if the project no longer wants them; remove their Quality Gate commands in the same change. Keep mode tooling if tracker/full is used. Keep a functioning application gate rather than leaving references to removed checks.

Upgrading from 2.x changes canonical ownership and adds setup/configuration; follow [.lean/CHANGELOG.md](.lean/CHANGELOG.md) before replacing files.
