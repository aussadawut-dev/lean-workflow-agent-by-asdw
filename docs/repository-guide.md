# Repository layout, customization and verification

[Back to README](../README.md)

Run CLI examples from the repository root.

## Repository layout

```text
lean-workflow-agent-by-asdw/
├── AGENTS.md                      Shared contract and project additions
├── CLAUDE.md                      Claude entrypoint importing the contract
├── docs/                          User guides
│   ├── getting-started.md         Installation, modes and execution
│   ├── skills.md                  Commands and procedure intensity
│   ├── quality-and-runtime.md     Review, gates and runtime limits
│   ├── maintenance.md             Compression, upgrades and cleanup
│   ├── repository-guide.md        Layout, customization and verification
│   ├── submodules.md              Application submodule setup
│   ├── workflow-overview.md       Complete workflow sequence
│   ├── tracker.md                 Worksets and mode transitions
│   ├── queue.md                   Task ownership, leases and cleanup
│   ├── spawn.md                   Controller, worker and reviewer sequences
│   ├── models.md                  Model selection and reasoning effort
│   └── takeover-workflow.md       Audit, decisions and workflow migration
├── .lean/                         Portable workflow baseline
│   ├── PROJECT.md                 Project-owned facts, commands and gate
│   ├── config.json                Project-owned mode and execution choice
│   ├── skill-effort.json          Optional project-owned procedure preferences
│   ├── README.md                  Policy router
│   ├── CUSTOMIZING.md             Import, ownership and upgrade guidance
│   ├── LICENSE                    Workflow notice for downstream imports
│   ├── CHANGELOG.md               Versions and migrations
│   ├── policy/                    Portable workflow rules
│   ├── skills/                    Canonical skills and resources
│   ├── roles/                     Shared reviewer instructions
│   ├── templates/                 Generic tracker and queue templates
│   ├── scripts/                   Shared gate, mode/lease tooling and checks
│   └── tests/                     Workflow behavior and regression tests
├── .claude/                       Claude runtime integration
│   ├── settings.json              Claude hook and permission settings
│   ├── hooks/                     SessionStart and Quality Gate hooks
│   ├── agents/
│   │   └── reviewer.md            Claude reviewer entrypoint
│   └── skills/                    Per-skill links to .lean/skills/
├── .agents/                       Codex integration
│   └── skills/                    Per-skill links to .lean/skills/
└── .github/                       GitHub integration
    ├── workflows/
    │   └── lean-workflow.yml       Workflow self-checks in CI
    └── pull_request_template.md   PR Result Contract template
```

Tracking and queue record directories are created by their mode setup; `skill-effort.json` is created only when preferences are saved. No example task history, procedure preferences or runtime leases ship with the template.

## Importing, customizing and upgrading

For an existing project, follow [.lean/CUSTOMIZING.md](../.lean/CUSTOMIZING.md). Merge entrypoints, settings, gitignore and CI. Preserve your project's owner, facts, accepted scope, configured mode/execution, procedure preferences, gates, records, custom agents and skills. Import the canonical skills, policy, scripts, registry and discovery links together; keep the existing optional-pack selection and each target's settings.

Put shared project overrides below `## Project additions` in `AGENTS.md`; keep Claude-specific additions in `CLAUDE.md`. Retain [.lean/LICENSE](../.lean/LICENSE) for the copied workflow alongside your own project license. Read [.lean/CHANGELOG.md](../.lean/CHANGELOG.md) before crossing versions, especially the 2.x migration to shared AGENTS authority.

The root README and CONTRIBUTING describe the template and may be replaced downstream. Workflow self-tests/CI can be removed if no longer wanted; remove their gate commands too. Keep mode tooling when tracker/full is used and retain a functioning application gate.

## Verify the workflow

Run from a Git working tree:

```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-hooks.sh
python3 .lean/scripts/workflow.py --root . check
python3 .lean/scripts/model_catalog.py --root . check
python3 -m unittest discover -s .lean/tests -p 'test_*.py'
```

For contribution expectations, see [CONTRIBUTING.md](../CONTRIBUTING.md). The project is distributed under the [MIT License](../LICENSE); preserve its notice when redistributing the workflow.
