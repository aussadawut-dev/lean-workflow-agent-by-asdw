# Getting started

[Back to README](../README.md)

Run the examples from the repository root.

## Requirements

macOS, Linux or WSL with Git and Python **3.9+**. Lean uses only the Python standard library; locks use Unix `fcntl`, so native Windows is unsupported. Set up your coding agents (Claude Code, Codex, agy) separately; Lean needs no paid service of its own and spawns provider CLIs only through your subscription login.

## Start a new project

```sh
git clone https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git my-project
cd my-project
python3 .lean/bin/lean --help
```

Open the project in Claude Code and run `/lean-init` (Codex: `$lean-init`; agy: ask it to follow `.lean/skills/lean-init/SKILL.md`). It reads real project facts, records your mode and execution choice, checks the model list against the CLIs you have, and fills `.lean/PROJECT.md`.

Already have a project? Follow [.lean/CUSTOMIZING.md](../.lean/CUSTOMIZING.md). Coming from 4.x? Follow [migrating to v5](migrating-to-v5.md).

## Configure without an agent

```sh
python3 .lean/bin/lean mode configure tracker --execution direct
python3 .lean/bin/lean mode show
python3 .lean/bin/lean mode check
python3 .lean/bin/lean models check --live
python3 .lean/bin/lean gate mode auto
```

`lean mode configure` creates `docs/tracking/` for tracker and full modes and `.agents/queue/` for full mode, and adds `.agent-runtime/` to `.gitignore`. Then put your project's deterministic checks between the gate markers in `.lean/PROJECT.md`, one command per line, and run `python3 .lean/bin/lean gate run`.

## Watch progress

Agents report their phase with `lean progress set`, and the bar appears in their replies. To see it live:

- Claude Code shows it in the status line (configured in `.claude/settings.json`).
- Any terminal: `python3 .lean/bin/lean watch` in a second pane (tmux, a split terminal). This is the live view for Codex and agy, which have no custom status line.
- `python3 .lean/bin/lean status` prints it once.

## Providers at a glance

| | Claude Code | Codex | agy |
|---|---|---|---|
| Skills | `/name` via `.claude/skills/` | `$name` via `.agents/skills/` | read `.lean/skills/<name>/SKILL.md` |
| Contract guard | PreToolUse hook | PreToolUse hook (after hook trust) | none: declare and follow the contract |
| Quality Gate | Stop hook | Stop hook (after hook trust) or `lean gate run` | `lean gate run` |
| Live progress | status line, replies | replies, Stop message, `lean watch` | replies, `lean watch` |
| Spawning | Agent tool or `lean spawn run` | `spawn_agent` or `lean spawn run` | `lean spawn run` |
