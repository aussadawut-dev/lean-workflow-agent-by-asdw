# Lean Workflow Agent by ASDW

I built this because I want a coding agent to understand the work, check what it changed, and explain why the task is done. This is the workflow I use for that, shared as a template you can bring into your own project.

It works with **Claude Code and Codex**, with one shared set of rules and skills. Use it with your own stack.

**Baseline 4.15.0** · [MIT License](LICENSE)

This release shows numbered Quality Gate progress with elapsed times on direct runs while Stops stay quiet, and makes the 4.14.0 mid-turn rule work in Claude Code: a prompt typed while the agent works keeps the Task Contract, checked live in Claude Code and Codex. See the [4.15.0 release notes](.lean/CHANGELOG.md#4150--2026-10-23) for changes and upgrade notes.

The idea is simple: **agree on the work → implement → test → validate → review → finish with evidence**. Use the steps the task needs. You do not have to call every skill or read every file to get started.

## What you get

- A shared contract for Claude and Codex, with skills maintained in one place.
- A short statement of risk, quality and acceptance before the agent changes files.
- Meaningful tests for behavior changes. For bugs, a regression test that fails before the fix and passes afterward.
- Review at the depth the work needs, followed by a Quality Gate using your project's checks.
- Three modes: keep evidence in the chat, keep a workset across sessions, or add a queue with explicit ownership.
- Nine core skills, nine optional skills, and `standard` / `high` / `ultra` procedure intensity.
- Gate locking to avoid overlapping runs, and history checks to avoid reusing task IDs.
- Worker assignments with a turn budget, required tests and a handoff when the budget runs out.

The template starts with unconfigured `standard` mode and `direct` execution. The portable workflow assets exclude project task history and leases. Mode, execution, model choice and review depth are separate settings.

## Quick start

You need **macOS, Linux or WSL**, Bash, Git, Python **3.9+**, and ShellCheck for the workflow's lint checks. Have your coding agent set up separately.

Use GitHub's **Use this template** action if the repository is enabled as a template, or clone it and change the remote to your own repository:

```sh
git clone https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git my-project
cd my-project
```

Open the project in your agent:

| What you want to do | Claude Code | Codex |
|---|---|---|
| Set up the project | `/lean-init` | `$lean-init` |
| Start a task | `/lean-task <task description>` | `$lean-task <task description>` |

`lean-init` reads the project, records your mode and execution choice, and helps fill [.lean/PROJECT.md](.lean/PROJECT.md) with real facts and commands. Add your application's checks there: the checks shipped in this template validate Lean itself.

Already have a project? Follow the [import guide](.lean/CUSTOMIZING.md). Want to keep Lean outside the application repository? See [application submodules](docs/submodules.md).

## Everyday use

Tell the agent what you want to change and how you will know it works. For example:

```text
# Claude Code
/lean-task Fix expired queue leases; add a regression test and run the project checks

# Codex
$lean-task Fix expired queue leases; add a regression test and run the project checks
```

The agent states a Task Contract, clears up important open decisions, does the accepted work, runs tests and validation, reviews the changes, and checks whether it can finish. It keeps decisions you have already made. It comes back to you when the scope changes or an important decision needs your input.

A clear implementation request accepts the scope it names, so routine work can continue. Scope planning pauses when the request is ambiguous, a material decision is open, risk is HIGH, or you asked only for a spec or analysis. Before edits, the agent states an observable check, for example:

```text
Contract: risk=MEDIUM quality=STANDARD acceptance=expired queue claims can be reclaimed and the regression test passes
```

You can also call a skill for just one part of the work:

| What you want to do | Claude Code | Codex |
|---|---|---|
| Make the requirement clear | `/lean-scope <requirement>` | `$lean-scope <requirement>` |
| Research and compare options | `/lean-research <question>` | `$lean-research <question>` |
| Find gaps in a plan before coding | `/lean-grill <plan>` | `$lean-grill <plan>` |
| Review the current changes | `/lean-review` | `$lean-review` |
| Check whether the task can finish | `/lean-gate` | `$lean-gate` |
| Delegate a bounded task | `/lean-agents <task>` | `$lean-agents <task>` |

Claude uses `/skill-name`. Codex uses `$skill-name` or its skill picker. Both read the same canonical skills. See the [full command guide](docs/skills.md).

## Choose a workflow mode

Start with the amount of record keeping you need:

| Mode | What it keeps | When to use it |
|---|---|---|
| `standard` | Contract, tests, validation, review and gate; evidence stays in the chat. | You want a simple start with fewer documents. |
| `tracker` | A workset for each non-trivial task in `docs/tracking/`. | You want to pick up the work in another session. |
| `full` | Tracker plus queue items, scope ownership and lease claims. | You need explicit ownership for workers in one checkout. |

Choose during `lean-init`, or run this from the repository root:

```sh
python3 .lean/scripts/workflow.py configure tracker --execution direct
python3 .lean/scripts/workflow.py show
python3 .lean/scripts/workflow.py check
```

Execution is a separate choice. `direct` means the active agent does the work. `delegated` means it acts as Controller, assigns a bounded task to a worker, then validates and integrates the result. Parallel workers need explicit user intent, independent tasks and separate file ownership.

Every mode keeps the same test and review requirements. HIGH-depth review needs an independent reviewer with either execution choice. For setup and mode changes, see [getting started](docs/getting-started.md) and [tracker transitions](docs/tracker.md).

## Keep worker assignments bounded

The [multi-agent procedure](.lean/skills/lean-agents/SKILL.md) sizes each assignment to a few files and about **50 turns**. A turn is a model request; parallel tool calls in one turn count once. Split larger assignments by component or layer before dispatch, and keep a slice that already fits whole. Choose capable model and effort settings for each assignment under the [model policy](.lean/policy/MODELS.md); spawn when required or cheaper than finishing in the active session.

The Controller's brief names the allowed files, acceptance checks, required tests, dependencies and budget. Workers locate relevant lines before reading, edit the needed parts, run focused tests while iterating and run their full checks before handoff. A budget never removes required behavior tests, including a page- or integration-level test for user-visible behavior; split the slice when needed.

When the budget runs out, the worker returns a consistent partial result with changed files, check status and remaining steps. The Controller sends unfinished work to a fresh worker with a new bounded brief. Resuming a spent worker is reserved for finishing its handoff report or recovering from a transient runtime error.

Runtime enforcement differs. Claude roles can back the budget with `maxTurns` and `autoCompactWindow`; keep the brief's turn budget below the turn cap. Codex `spawn_agent` has no per-spawn turn cap, so its brief carries the budget. A hard cap can interrupt an edit: the Controller checks `git status` and the diff of assigned files before accepting a result, and treats a missing report as partial work.

In `full` mode, a Controller holding a claim heartbeats it before dispatch and when the worker returns. A worker that may outlast the remaining lease gets its own item and claim. Expired claims need a new claim request ID; unfinished worker claims must be released or claimed again before redispatch. See [queue ownership and leases](docs/queue.md).

## Set how much detail a skill uses

Choose `standard`, `high` or `ultra` to adjust how thoroughly a skill follows its procedure. For example, research can compare more relevant options, or scope can cover more failure cases.

This setting is separate from model reasoning effort, task quality, workflow mode and execution.

| What you want to do | Claude Code | Codex |
|---|---|---|
| See saved settings | `/lean-effort` | `$lean-effort` |
| Set a default for all skills | `/lean-effort high` | `$lean-effort high` |
| Set research separately | `/lean-effort ultra lean-research` | `$lean-effort ultra lean-research` |
| Reset research to the default | `/lean-effort reset lean-research` | `$lean-effort reset lean-research` |
| Reset everything to standard | `/lean-effort reset` | `$lean-effort reset` |

For just one task, say “use scope high and research ultra for this task.” That choice stays with the task. Saved preferences go in optional `.lean/skill-effort.json`. Setting a global level clears individual overrides; resetting one skill restores inheritance. See [settings and CLI examples](docs/skills.md#optional-skill-levels).

## Enable optional skills

The nine core skills are ready by default. To expose the nine optional skills, run these commands from the repository root, then reload your runtime's skills:

```sh
python3 .lean/scripts/skill_pack.py enable
python3 .lean/scripts/skill_pack.py status
# Hide the optional skills again:
python3 .lean/scripts/skill_pack.py disable
```

A few useful starting points after enabling them:

| What you want to do | Claude Code | Codex |
|---|---|---|
| Preview a workflow update | `/lean-update` | `$lean-update` |
| Preview repository cleanup | `/lean-prune repo` | `$lean-prune repo` |
| Preview shorter workflow prose | `/lean-compress workflow --preview` | `$lean-compress workflow --preview` |
| Add an application submodule | `/lean-target <remote url>` | `$lean-target <remote url>` |
| Prepare deployment and rollback plans | `/lean-playbook` | `$lean-playbook` |

The pack also covers project standards, audits, model research, queue cleanup and workflow takeover. Updates, repository cleanup and prose compression start with a preview. Applying them follows the accepted scope and each procedure's approval rules. Playbook preparation writes project plans; `check` inspects readiness, while explicit `deploy` or `rollback` requests execute the resolved plan. See [deployment and rollback](docs/skills.md#deployment-and-rollback-playbooks).

See [all 18 skills](docs/skills.md#core-and-optional-commands) and the [maintenance guide](docs/maintenance.md).

## Before calling a task done

Put your application's real test, lint, build and typecheck commands in [.lean/PROJECT.md](.lean/PROJECT.md), between its existing gate markers. Each command must exit non-zero when it fails.

You can run the shared checks yourself:

```sh
bash .lean/scripts/quality-gate.sh --root .
```

Claude uses its Stop hook under the shared auto/manual policy. Codex runs the gate explicitly, or through its lifecycle adapter once the runtime has trusted and activated it.

Passing commands is one part of completion. The result also needs to meet the acceptance criteria, include the required tests and cover the final changes in review. HIGH-depth work needs a matching independent-review receipt. If a required tool or piece of evidence is missing, report the blocker.

The reviewer records that receipt in `.agent-runtime/review.json` in the checkout being gated. Each worktree has its own runtime evidence; a receipt in another worktree does not satisfy its gate. The receipt must match the Task Contract and current shipping state. Later content changes require a new review; staging or committing the complete reviewed content can preserve the receipt.

To validate HIGH-depth work, supply the exact Task Contract used for its review:

```sh
bash .lean/scripts/quality-gate.sh --root . --require-review --contract '<exact Task Contract>'
```

In `auto` or `auto_fixloop` mode, the Stop adapters run the shared checks. In `manual` or `manual_fixloop` mode, automatic Stops report `NOT_RUN` and starting the full gate requires user authorization; explicit gate runs still execute, and the task remains unfinished until validation and required review pass. In `auto_fixloop` and `manual_fixloop`, once the gate runs, the agent auto-loops over actionable failures until the gate passes without asking between rounds, stopping only for genuine questions or missing tools. A Stop released as `UNVERIFIED` also remains blocked. See the [shared quality policy](.lean/policy/QUALITY.md).

See [quality and runtime details](docs/quality-and-runtime.md) and [workflow verification commands](docs/repository-guide.md#verify-the-workflow).

## Read more when you need it

| Guide | What it covers |
|---|---|
| [Getting started](docs/getting-started.md) | Requirements, installation, modes and execution. |
| [Workflow overview](docs/workflow-overview.md) | The path from a request to completion. |
| [Skills and intensity](docs/skills.md) | All commands, optional discovery and skill settings. |
| [Quality and runtime](docs/quality-and-runtime.md) | Tests, review, gates, hooks and their limits. |
| [Tracker](docs/tracker.md) | Worksets across sessions and mode changes. |
| [Queue](docs/queue.md) | Ownership, claims, leases and history. |
| [Delegation](docs/spawn.md) | Controller, worker and reviewer responsibilities. |
| [Models and effort](docs/models.md) | Choosing a model, reasoning effort and catalog updates. |
| [Maintenance](docs/maintenance.md) | Prose compression, updates and cleanup. |
| [Workflow takeover](docs/takeover-workflow.md) | Planning, migration and recovery. |
| [Application submodules](docs/submodules.md) | Keeping application code separate from Lean. |
| [Repository guide](docs/repository-guide.md) | File layout, customization and verification. |
| [Developing Lean](docs/workflow-development.md) | Internal tools and test coverage. |

Want to contribute? Read [CONTRIBUTING.md](CONTRIBUTING.md). Version history and migration notes are in [.lean/CHANGELOG.md](.lean/CHANGELOG.md).
