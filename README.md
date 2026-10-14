# Lean Workflow Agent by ASDW

A reusable workflow for Claude and Codex: clear task contracts, meaningful tests, risk-based review and evidence before completion. Use it with your own application stack.

**Baseline 4.1.0** · [Latest published extension: v4.1.0-skill-effort.1](https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw/tree/v4.1.0-skill-effort.1)

## What you get

- One shared contract and skill library for Claude and Codex.
- A complete task flow: scope → implementation → tests → validation → review → Quality Gate.
- Three workflow modes: `standard` for session evidence, `tracker` for persistent worksets, and `full` for queue ownership and leases.
- Nine core skills, ten optional skills, and shared `standard` / `high` / `ultra` procedure intensity.
- Gate locking and tracker-history guards to prevent overlapping gate runs and reused task IDs.

Mode, execution strategy, model choice and review depth are separate. The template starts with unconfigured `standard` mode and `direct` execution, without task history or leases.

## Quick start

Requires macOS, Linux or WSL, Bash, Git and Python **3.9+**. Install ShellCheck for the workflow's lint gate.

```sh
git clone https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git my-project
cd my-project
```

Use GitHub’s **Use this template** action for a new repository, or change the cloned repository’s remote to your own. Open the project in your coding agent:

| Runtime | Set up the project | Start work |
|---|---|---|
| Claude Code | `/lean-init` | `/lean-task <task description>` |
| Codex | `$lean-init` | `$lean-task <task description>` |

Setup records your mode and execution choice. Fill [.lean/PROJECT.md](.lean/PROJECT.md) with your application's real commands and Quality Gate; the shipped checks validate the workflow itself.

For an existing repository, follow the [import guide](.lean/CUSTOMIZING.md). To keep Lean outside the application repository, use [application submodules](docs/submodules.md).

## Everyday use

Start with a concrete outcome and acceptance criteria. For example:

```text
# Claude Code
/lean-task Fix expired queue leases; add a regression test and run the project checks

# Codex
$lean-task Fix expired queue leases; add a regression test and run the project checks
```

The agent states a Task Contract, resolves material scope decisions, implements the accepted work, runs tests and validation, reviews the changes and checks completion. It reuses accepted decisions and asks when a material decision or scope change needs your input. You do not need to invoke every step manually.

Use an individual skill when you want to focus on one stage:

| Purpose | Claude Code | Codex |
|---|---|---|
| Define the requirement | `/lean-scope <requirement>` | `$lean-scope <requirement>` |
| Compare approaches | `/lean-research <question>` | `$lean-research <question>` |
| Challenge a plan before implementation | `/lean-grill <plan>` | `$lean-grill <plan>` |
| Review the current change | `/lean-review` | `$lean-review` |
| Check whether work is complete | `/lean-gate` | `$lean-gate` |
| Coordinate bounded delegation | `/lean-multi-agent <task>` | `$lean-multi-agent <task>` |

Both runtimes use the same canonical skills. In Codex, invoke them with `$` or use the skill picker. See the [complete command reference](docs/skills.md).

## Choose a workflow mode

| Mode | What it adds | Choose it when |
|---|---|---|
| `standard` | Contract, tests, validation, review and gate; evidence stays in the session. | You want minimal record keeping. |
| `tracker` | A persistent workset for each non-trivial task under `docs/tracking/`. | Work and decisions need to survive between sessions. |
| `full` | Queue items, scope ownership and lease claims. | Workers need explicit task ownership. |

Select a mode during `lean-init`, or configure it from the repository root:

```sh
python3 .lean/scripts/workflow.py configure tracker --execution direct
python3 .lean/scripts/workflow.py show
python3 .lean/scripts/workflow.py check
```

Execution is independent: `direct` lets the active agent implement; `delegated` makes it a Controller dispatching bounded work to an available worker. Parallel workers require explicit user intent and independent file ownership. Every mode keeps the same test and review obligations; HIGH-depth review always requires an independent reviewer.

Mode downgrades use a guarded preview/apply procedure. See [setup and execution](docs/getting-started.md) and [mode transitions](docs/tracker.md).

## Set skill procedure intensity

Use `standard`, `high` or `ultra` to control how thoroughly a skill performs its procedure. This is separate from model reasoning effort, task quality, workflow mode and execution routing.

| Action | Claude Code | Codex |
|---|---|---|
| Inspect saved settings | `/lean-skill-effort` | `$lean-skill-effort` |
| Save a default for all skills | `/lean-skill-effort high` | `$lean-skill-effort high` |
| Override one skill | `/lean-skill-effort ultra lean-research` | `$lean-skill-effort ultra lean-research` |
| Remove one override | `/lean-skill-effort reset lean-research` | `$lean-skill-effort reset lean-research` |
| Reset all skills to standard | `/lean-skill-effort reset` | `$lean-skill-effort reset` |

For one task, say “use scope high and research ultra for this task”; task-specific choices are not saved as project defaults. Saved choices live in optional project-owned `.lean/skill-effort.json`. A global setting clears named overrides; a named reset restores inheritance. See [intensity rules and CLI examples](docs/skills.md#optional-skill-levels).

## Enable optional skills

Nine core skills are available by default. Enable the ten optional skills from the repository root, then reload your runtime’s skills:

```sh
python3 .lean/scripts/skill_pack.py enable
python3 .lean/scripts/skill_pack.py status
# Remove optional discovery links again:
python3 .lean/scripts/skill_pack.py disable
```

After enabling, common starting points are:

| Purpose | Claude Code | Codex |
|---|---|---|
| Preview a workflow update | `/lean-update-workflow` | `$lean-update-workflow` |
| Preview repository cleanup | `/lean-clean-repo` | `$lean-clean-repo` |
| Preview prose compression | `/lean-compress workflow --preview` | `$lean-compress workflow --preview` |
| Keep application code in a submodule | `/lean-use-submodule <remote url>` | `$lean-use-submodule <remote url>` |

The pack also includes model catalog refresh, queue cleanup and workflow takeover. Updates, cleanup and compression start with a preview; applying changes follows their scope and approval rules. See [all optional commands](docs/skills.md#core-and-optional-commands) and the [maintenance guide](docs/maintenance.md).

## Validate before completion

Put your application’s real test, lint, build and typecheck commands in [.lean/PROJECT.md](.lean/PROJECT.md), with gate commands between its existing markers. Each command must exit non-zero on failure. Behavior changes need meaningful tests; bug fixes need a regression test shown failing before the fix and passing afterward.

Claude runs the shared gate through its Stop hook. Codex runs it explicitly; you can also run it from the repository root:

```sh
bash .lean/scripts/quality-gate.sh --root .
```

This runs the configured gate checks. Completion also requires acceptance evidence and the required review; HIGH work needs a matching independent-review receipt. See [quality and runtime details](docs/quality-and-runtime.md) and [workflow verification commands](docs/repository-guide.md#verify-the-workflow).

## Documentation

| Guide | Read it for |
|---|---|
| [Getting started and modes](docs/getting-started.md) | Requirements, installation, agent-free setup and execution routing. |
| [Workflow overview](docs/workflow-overview.md) | The complete task sequence from request to completion. |
| [Skills and intensity](docs/skills.md) | All 19 commands, optional discovery and skill-effort settings. |
| [Quality and runtime](docs/quality-and-runtime.md) | Tests, review, gate locking, caching and Claude/Codex integration limits. |
| [Tracker](docs/tracker.md) | Persistent worksets, statuses and mode transitions. |
| [Queue](docs/queue.md) | Ownership, claims, leases, dependencies and history. |
| [Delegation](docs/spawn.md) | Controller, worker and independent reviewer sequences. |
| [Models and effort](docs/models.md) | Model selection, reasoning effort and catalog refresh. |
| [Maintenance](docs/maintenance.md) | Prose compression, workflow upgrades and repository cleanup. |
| [Workflow takeover](docs/takeover-workflow.md) | Audit and migrate an existing workflow with recovery. |
| [Application submodules](docs/submodules.md) | Separate application code from Lean tools and project records. |
| [Repository guide](docs/repository-guide.md) | File layout, customization, upgrades and verification commands. |

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute and [.lean/CHANGELOG.md](.lean/CHANGELOG.md) for baseline history. Distributed under the [MIT License](LICENSE).
