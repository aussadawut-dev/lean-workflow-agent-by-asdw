# Lean Workflow Agent by ASDW

I built this because I want a coding agent to understand the work, check what it changed, and explain why the task is done. This is the workflow I use for that, shared as a template you can bring into your own project.

It works with **Claude Code, Codex and agy (Antigravity)**, with one shared set of rules and skills and one command line, `lean`. Use it with your own stack. Everything is free: Python's standard library and Git, plus the subscriptions you already have.

**Baseline 5.2.1** · [MIT License](LICENSE)

5.0.0 rebuilds the workflow around one `lean` command, shows progress as a bar on every surface, runs only the tests a change can affect, and spawns sized agents from a per-provider model list. It is a major release: upgrading from 4.x moves files and commands. See the [5.0.0 release notes](.lean/CHANGELOG.md#500--2026-10-27) and [migrating to v5](docs/migrating-to-v5.md).

The idea is simple: **agree on the work → implement → test → validate → review → finish with evidence**. Use the steps the task needs.

```text
███████████████░░░░░ 76% review — add expired-lease regression
```

## What you get

- A shared contract for every agent, with skills maintained in one place.
- A short statement of risk, quality and acceptance before the agent changes files.
- A progress bar for each task, in the agent's replies, the Claude status line, `lean watch`, test and gate runs, and one bar per spawned agent.
- Meaningful tests for behavior changes, and only the tests a change can affect while you work; the full suite runs in CI and at release.
- Review at the depth the work needs, followed by a Quality Gate using your project's checks.
- Agents sized 3S to 3XL (eight sizes) from a per-provider model list: one at a time by default, as many as the work allows with `/lean-agents`, or exactly the ones you name.
- Three modes: keep evidence in the chat, keep a workset across sessions, or add a queue with explicit ownership.

## Quick start

You need **macOS, Linux or WSL**, Git and Python **3.9+**. Have your coding agent set up separately.

```sh
git clone https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git my-project
cd my-project
python3 .lean/bin/lean --help
```

Open the project in your agent:

| What you want to do | Claude Code | Codex | agy |
|---|---|---|---|
| Set up the project | `/lean-init` | `$lean-init` | ask for `lean-init` |
| Start a task | `/lean-task <task>` | `$lean-task <task>` | ask for `lean-task` |

`lean-init` records your mode and execution choice and fills [.lean/PROJECT.md](.lean/PROJECT.md) with real facts and commands. Add your application's checks there: the checks shipped in this template validate Lean itself. Already have a project? Follow the [import guide](.lean/CUSTOMIZING.md).

## Everyday use

Tell the agent what you want to change and how you will know it works:

```text
/lean-task Fix expired queue leases; add a regression test and run the project checks
```

The agent states a Task Contract, clears up important open decisions, does the accepted work, runs tests and validation, reviews the changes, and checks whether it can finish, showing the bar as it moves through each phase. It comes back to you when the scope changes or an important decision needs your input.

```text
Contract: risk=MEDIUM quality=STANDARD acceptance=expired queue claims can be reclaimed and the regression test passes
```

Call a skill for one part of the work (Claude `/name`, Codex `$name`):

| What you want to do | Skill |
|---|---|
| Make the requirement clear | `lean-scope <requirement>` |
| Research and compare options | `lean-research <question>` |
| Find gaps in a plan before coding | `lean-grill <plan>` |
| Run independent tasks in parallel | `lean-agents [<model> xN] <task>` |
| Review the current changes | `lean-review` |
| Check whether the task can finish | `lean-gate` |
| Set procedure depth | `lean-effort [standard\|high\|ultra]` |
| Keep an application in its own repository | `lean-target <remote url>` |
| Update Lean | `lean-update` |
| Refresh the model list from an eval | `lean-model-update` |

See the [skill guide](docs/skills.md).

## The `lean` command

```sh
python3 .lean/bin/lean status            # mode, gate and the progress bar
python3 .lean/bin/lean watch             # live progress in a second pane (Codex, agy, any terminal)
python3 .lean/bin/lean test --changed    # only the tests your change can affect
python3 .lean/bin/lean gate run          # the project's Quality Gate
python3 .lean/bin/lean models            # the model list per provider
python3 .lean/bin/lean log --summary     # time per phase, gate/test/agent/review counts
python3 .lean/bin/lean spawn plan --tasks tasks.json --level max
```

## Agents and models

`.lean/models.json` maps eight sizes (`3S` to `3XL`) to models for each provider. Three levels decide how many agents run:

| You say | Agents |
|---|---|
| nothing | at most one at a time (`max_agents`), sized to the task, and only when cheaper than finishing in the session |
| `/lean-agents` | one per task that can run in parallel |
| `/lean-agents sonnet x3` | up to three at once, all on that model (more tasks run in later waves) |

Agents run inside the session (the runtime's subagent tool) or as separate processes in their own git worktrees (`lean spawn run`), which remove metered API keys so the provider CLIs use your subscription. See [agents and models](docs/agents-and-models.md).

## Choose a workflow mode

| Mode | What it keeps | When to use it |
|---|---|---|
| `standard` | Contract, tests, validation, review and gate; evidence stays in the chat. | You want a simple start. |
| `tracker` | A workset for each non-trivial task in `docs/tracking/`. | You want to pick up the work in another session. |
| `full` | Tracker plus queue items, scope ownership and lease claims. | You need explicit ownership for workers in one checkout. |

```sh
python3 .lean/bin/lean mode configure tracker --execution direct
python3 .lean/bin/lean mode check
```

Execution is a separate choice: `direct` means the active agent does the work; `delegated` means it acts as Controller and assigns bounded tasks to workers. Every mode keeps the same test and review requirements. See the [workflow guide](docs/workflow.md).

## Guides

- [Getting started](docs/getting-started.md)
- [Workflow, modes, trackers and queue](docs/workflow.md)
- [Quality Gate, hooks and progress](docs/quality-and-runtime.md)
- [Agents and models](docs/agents-and-models.md)
- [Application targets (submodules)](docs/targets.md)
- [Skills](docs/skills.md)
- [Migrating to v5](docs/migrating-to-v5.md)
- [Developing Lean](docs/development.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
