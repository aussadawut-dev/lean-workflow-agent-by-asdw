# Getting started and workflow modes

[Back to README](../README.md)

Run the CLI examples from the repository root.

## Requirements

You need macOS, Linux or WSL with Bash, Git and Python **3.9+**. The Python tools use only the standard library. Lease locking uses Unix `fcntl`, so native Windows is currently unsupported. Install ShellCheck for the workflow's own lint gate.

Set up your coding agent separately. The template has no application dependencies and needs no paid service of its own. Agent access and usage follow your account and runtime settings.

## Start a new project

Use GitHub's **Use this template** action if it is enabled, or clone the repository and change the remote to your own:

```sh
git clone https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git my-project
cd my-project
```

If you want the files without the Git history and already have Node/npm, you can also use:

```sh
npx degit aussadawut-dev/lean-workflow-agent-by-asdw my-project
cd my-project
git init
```

Open the project in Claude Code and run `/lean-init`, or use `$lean-init` in Codex. It reads real project facts, records your mode and execution choice, and helps fill `.lean/PROJECT.md`.

Both runtimes discover skills through links to `.lean/skills/`. Nine core skills are enabled by default. Run `python3 .lean/scripts/skill_pack.py enable` to expose the ten optional skills, then reload the runtime's skill list. `disable` removes only the optional discovery links. See [.lean/OPTIONAL.md](../.lean/OPTIONAL.md).

Edit skills at their canonical source. Adding a Lean skill also means registering its files and assigning it to core or optional discovery. If your runtime cannot discover a skill, ask the agent to read its `SKILL.md` and follow the procedure. Other agents can use `AGENTS.md` and the shared procedures manually; native integrations are supplied for Claude and Codex.

## Configure without an agent

Pick a mode, inspect it, then check it:

```sh
python3 .lean/scripts/workflow.py configure standard
python3 .lean/scripts/workflow.py show
python3 .lean/scripts/workflow.py check
```

For tracking with delegated execution:

```sh
python3 .lean/scripts/workflow.py configure tracker --execution delegated
```

Leaving out `--execution` keeps the current setting. Configuration lives in project-owned `.lean/config.json`. Agents follow that choice across tasks.

Fill `.lean/PROJECT.md` with your application's real test, lint, build and typecheck commands. Put gate commands between the existing markers, one per line. Each must exit non-zero on failure.

The shipped turn gate checks workflow integrity. The full regression suite runs before shipping workflow behavior changes and in CI. Add your application's checks when you bring in application code. A missing or empty project gate blocks completion until configured.

## Workflow modes

| Mode | How it keeps work | When it helps |
|---|---|---|
| `standard` | Contract → work → tests → validation → review → gate. Evidence stays in the chat. | You want less record keeping. |
| `tracker` | Adds one workset for each non-trivial task in `docs/tracking/`. | You want decisions and progress to survive a new session. |
| `full` | Adds queue items, scope ownership and local lease claims. | Workers need explicit ownership in one checkout. |

All modes keep the same testing, quality and review requirements. Trivial tasks need no new tracker or queue item. Work within a claimed scope still follows its ownership rules.

In tracker/full mode, `tracker new` rejects IDs already used by a current tracker or Markdown/text records under `docs/history/agent-workflow/`, including nested history. Pick a new ID and keep the old history.

## Execution is a separate choice

| Execution | Who does the work |
|---|---|
| `direct` | The active agent implements and coordinates the task. This is the default. |
| `delegated` | The active agent becomes Controller and assigns bounded work to a capable worker. |

Delegated execution needs available worker tooling. Parallel workers also need explicit user intent, independent tasks and separate file ownership. HIGH-depth review requires an independent reviewer with either execution setting.
