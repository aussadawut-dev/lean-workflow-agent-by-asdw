# Repository layout, customization and verification

[Back to README](../README.md)

Run the CLI examples from the repository root.

## Repository layout

Here is where the main pieces live:

```text
lean-workflow-agent-by-asdw/
├── AGENTS.md                      Shared contract and project additions
├── CLAUDE.md                      Claude entrypoint importing AGENTS
├── README.md                      Start here
├── CONTRIBUTING.md                How to contribute and validate changes
├── docs/                          Public guides
│   ├── getting-started.md         Setup, modes and execution
│   ├── workflow-overview.md       Request-to-completion sequence
│   ├── skills.md                  Commands and procedure intensity
│   ├── quality-and-runtime.md     Review, gates and runtime limits
│   ├── tracker.md                 Worksets and mode transitions
│   ├── queue.md                   Ownership, leases and history
│   ├── spawn.md                   Controller, worker and reviewer
│   ├── models.md                  Model selection and reasoning effort
│   ├── maintenance.md             Compression, updates and cleanup
│   ├── takeover-workflow.md       Workflow migration and recovery
│   ├── submodules.md              Application submodules
│   ├── repository-guide.md        This guide
│   └── workflow-development.md    Internal tools and test coverage
├── .lean/                         Portable workflow baseline
│   ├── PROJECT.md                 Project facts, commands and gate
│   ├── config.json                Project mode and execution
│   ├── skill-effort.json          Optional saved procedure preferences
│   ├── README.md                  Policy router
│   ├── CUSTOMIZING.md             Import, ownership and upgrade guidance
│   ├── OPTIONAL.md                Optional skill discovery
│   ├── LICENSE                    Notice to retain on import
│   ├── CHANGELOG.md               Versions and migration notes
│   ├── assets.json                Portable asset registry
│   ├── policy/                    Shared rules
│   ├── skills/                    Canonical skills and resources
│   ├── roles/                     Shared reviewer instructions
│   ├── templates/                 Generic record templates
│   ├── scripts/                   Gate, modes, leases and other tools
│   └── tests/                     Workflow and regression tests
├── .claude/                       Claude integration
│   ├── settings.json              Claude hooks and permissions
│   ├── hooks/                     SessionStart and Stop adapters
│   ├── agents/reviewer.md         Reviewer entrypoint
│   └── skills/                    Links to .lean/skills/
├── .agents/skills/                Codex skill discovery links
├── .codex/                        Codex lifecycle integration
│   ├── hooks.json                 Definitions requiring runtime trust
│   ├── hooks/                     SessionStart and Stop adapters
│   └── quality-gate.json          Optional local gate mode preference (auto|manual|auto_fixloop|manual_fixloop)
└── .github/
    ├── workflows/lean-workflow.yml Workflow self-checks in CI
    └── pull_request_template.md   PR Result Contract
```

Mode setup creates tracker and queue directories. `skill-effort.json` and `quality-gate.json` are optional preferences created when saved. The template contains no actual task history, saved procedure preferences or runtime leases.

## Importing, customizing and upgrading

For an existing project, follow [.lean/CUSTOMIZING.md](../.lean/CUSTOMIZING.md). Merge entrypoints, settings, gitignore and CI. Keep the project's owner, facts, accepted scope, mode/execution, preferences, gates, records, custom agents and skills.

Import canonical skills, policy, scripts, registry and discovery links together. Preserve the optional-pack choice and each target's settings. Put shared project overrides below `## Project additions` in `AGENTS.md`; keep Claude-specific additions in `CLAUDE.md`.

Keep [.lean/LICENSE](../.lean/LICENSE) alongside your own project license. Read [.lean/CHANGELOG.md](../.lean/CHANGELOG.md) before crossing versions, especially the 2.x move to shared AGENTS authority.

The root README and CONTRIBUTING describe this template; you can replace them for your application. You can remove workflow self-tests/CI if no longer wanted, along with their gate commands. Keep mode tooling if you use tracker/full, and retain a functioning application gate.

## Verify the workflow

From a Git working tree, the shared gate runs the configured PROJECT checks:

```sh
bash .lean/scripts/quality-gate.sh --root .
```

For the individual checks and full Python suite:

```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-hooks.sh
python3 .lean/scripts/workflow.py --root . check
python3 .lean/scripts/model_catalog.py --root . check
python3 -m unittest discover -s .lean/tests -p 'test_*.py'
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for test and review expectations. The project uses the [MIT License](../LICENSE); retain its notice when redistributing the workflow.
