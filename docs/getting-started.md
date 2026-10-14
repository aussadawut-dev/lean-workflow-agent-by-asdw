# Getting started and workflow modes

[Back to README](../README.md)

Run CLI examples from the repository root.

## Requirements

Use macOS, Linux or WSL with Bash, Git and Python **3.9+**. Python tooling uses only the standard library; lease locking uses Unix `fcntl`. Install ShellCheck to run the workflow's own lint gate. Native Windows is unsupported.

Your coding agent and its runtime are supplied separately. The template has no application dependencies and requires no paid service of its own; agent access and usage follow your runtime's settings.

## Start a new project

Use GitHub's **Use this template** action if the repository is enabled as a template, or clone it and change the remote for your own repository:

```sh
git clone https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git my-project
cd my-project
```

To copy the files without this repository's Git history, an optional Node/npm-based route is:

```sh
npx degit aussadawut-dev/lean-workflow-agent-by-asdw my-project
cd my-project
git init
```

Open the project in Claude Code and run `/lean-init`, or invoke `$lean-init` in Codex. It discovers actual project facts and commands, records the selected mode/execution, and helps fill `.lean/PROJECT.md`.

Both runtimes read canonical skills in `.lean/skills/`, through per-skill discovery links. Nine core procedures are enabled by default; `python3 .lean/scripts/skill_pack.py enable` adds the ten optional procedures, and `disable` removes only their discovery links. Reload runtime skills after toggling. See [.lean/OPTIONAL.md](../.lean/OPTIONAL.md). Edit the canonical files only; adding a Lean skill requires registering its canonical files and assigning it to core or optional discovery. If your runtime does not discover skills, ask the agent to read the relevant `SKILL.md` and follow its procedure. Other agents can follow `AGENTS.md` and the shared procedures manually; runtime integrations are provided for Claude and Codex.

## Configure without an agent

Choose one mode, then inspect and validate it:

```sh
python3 .lean/scripts/workflow.py configure standard
python3 .lean/scripts/workflow.py show
python3 .lean/scripts/workflow.py check
```

To enable tracking and delegation instead:

```sh
python3 .lean/scripts/workflow.py configure tracker --execution delegated
```

Omitting `--execution` preserves the current setting. Configuration belongs to the project in `.lean/config.json`; agents follow the recorded choice rather than selecting a mode for each task.

Fill `.lean/PROJECT.md` with your application's real test, lint, build and typecheck commands. Add gate commands between its existing markers, one command per line. Each must exit non-zero on failure. The shipped turn gate tests workflow integrity; the full regression suite runs before shipping behavior changes and in CI. Neither validates application code you add later. Missing/empty project gates block until configured.

## Workflow modes

| Mode | How work is managed | Useful when |
|---|---|---|
| `standard` | Task Contract → work → tests → validation → review → Quality Gate. Evidence stays in the session. | You want the core workflow with minimal record keeping. |
| `tracker` | Everything in standard, plus one workset document for each non-trivial task under `docs/tracking/`. | Decisions, progress and evidence need to survive between sessions. |
| `full` | Everything in tracker, plus queue items, scope ownership and local lease claims. | Multiple workers need explicit task ownership in one checkout. |

All three modes retain the same testing rules, quality floor and review requirements. A heavier mode adds coordination; it does not select a stronger model or a different quality level. Trivial tasks need no new tracker or queue item; work within an already claimed scope still follows ownership rules.

In tracker/full mode, `tracker new` rejects IDs already used by a current tracker or by Markdown/text records under `docs/history/agent-workflow/`, including nested history. Choose a new ID; retained history stays intact.

Execution is a separate choice:

| Execution | Who does the work |
|---|---|
| `direct` | The active agent implements and coordinates the task. This is the default. |
| `delegated` | The active agent acts as Controller and dispatches bounded work to a capable worker. |

Delegated execution requires available worker tooling. Parallel workers additionally require explicit user intent, independent tasks and exclusive file ownership. Independent HIGH-depth review is required with either execution setting.
