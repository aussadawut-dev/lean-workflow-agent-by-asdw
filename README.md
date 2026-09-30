# Lean Workflow Agent by ASDW

A repository starter for Claude (primary) with a quality-driven coding workflow. Other agents that read `AGENTS.md` follow the same contract.

## Start

Create a new repository from this one without its history:

- GitHub: **Use this template** button, or
- `npx degit aussadawut-dev/lean-workflow-agent-by-asdw my-project`, or
- `git clone` then `rm -rf .git && git init`

Then open it with Claude. That's it.

The first session asks one question -- which workflow mode the project runs -- and records the answer
in `.lean/PROJECT.md`. Nothing asks again.

- Claude reads `CLAUDE.md` (canonical) and `.claude/` (hooks, skills, reviewer subagent).
- Codex and other agents read `AGENTS.md`, which defers to `CLAUDE.md`.
- Workflow rules live in `.lean/`. Start at `.lean/README.md`.

Build your repository however you want. Lean Workflow does not prescribe language, framework, architecture, package manager, database, or deployment model.

As the project grows, agents fill in `.lean/PROJECT.md` with real commands and paths. Add your test/lint commands to its Quality Gate section to have the `Stop` hook enforce them.

## Headless and CI use

`claude -p` ignores `permissions.allow` in `.claude/settings.json` until the workspace is trusted. Open the repository once with interactive Claude and accept the trust dialog, or pass `--allowedTools` on the command line. Hooks, skills, and the reviewer subagent still load.

## Modes

How much process the workflow runs. Chosen once, on the first session, and recorded in the mode
block of `.lean/PROJECT.md`. Rules: `.lean/policy/MODES.md`.

| Mode | Adds |
|---|---|
| `standard` | Nothing. Contracts, tests, review, Quality Gate -- the workflow as written. |
| `tracker` | One tracking record per non-trivial task, committed under `.lean/tracker/`. |
| `full` | The record, and a task queue whose items must be claimed before work starts. |

Modes only add steps: none of them lowers the quality floor. To switch, edit the value in that block
by hand (`.lean/bin/mode.sh set <mode>` does the same thing) -- agents follow it and never change it
on their own.

`tracker` keeps the Result Contract on disk, one record per task:

```sh
.lean/bin/tracker.sh new "Rotate the signing keys" --contract "risk=HIGH quality=HIGH acceptance=..."
.lean/bin/tracker.sh current                        # the record still open
.lean/bin/tracker.sh state <record> DONE            # at the Quality Gate
```

`full` is for several sessions or machines working one backlog. Items live on their own git branch,
one file per item, and a claim is a push to it, so two sessions cannot both take the same item:

```sh
.lean/bin/queue.sh add "Rotate the signing keys"   # prints the item id
.lean/bin/queue.sh list                            # open items first
.lean/bin/queue.sh claim rotate-the-signing-keys   # exit 3: someone else has it
.lean/bin/queue.sh done rotate-the-signing-keys
```

## Claude commands

| Command | Use |
|---|---|
| `/lean-init` | Fill `.lean/PROJECT.md` from the real repository |
| `/lean-task <task>` | Start non-trivial work with a Task Contract |
| `/lean-review` | Review at the depth risk and quality require |
| `/lean-gate` | Run the Quality Gate and report DONE or not |

## Layout

Three zones. Each has one job and one owner.

```
CLAUDE.md               Entrypoint for Claude. The canonical contract.
AGENTS.md               Adapter for Codex and other agents. Defers to CLAUDE.md.
CONTRIBUTING.md         How to change the workflow files.

.lean/                  ZONE 1 - the workflow. Tool-agnostic; any agent can read it.
  README.md             Router: which rule file to read, and when.
  PROJECT.md            Context, commands, Quality Gate, workflow mode. <- yours to edit
  CHANGELOG.md          Workflow versions and upgrade steps.
  policy/               The rules. Replaced wholesale on upgrade.      <- do not edit
  bin/                  Tools a session runs: mode.sh, tracker.sh, queue.sh
  scripts/              check-structure.sh
  tests/                one per tool, plus test-hooks.sh

.claude/                ZONE 2 - Claude runtime. Paths are fixed by Claude Code.
  settings.json         Hooks and permissions.
  hooks/                quality-gate.sh (Stop), session-start.sh (SessionStart)
  skills/               /lean-init, /lean-task, /lean-review, /lean-gate
  agents/               reviewer subagent

.github/                ZONE 3 - GitHub platform only.
  workflows/            CI for the workflow files, nothing else.
  pull_request_template.md
```

Everything else belongs to your project. All three zone names are namespaced on purpose: your own
`scripts/`, `tests/`, `docs/`, and root `CHANGELOG.md` never collide with the workflow's.

## Checks

The workflow files test themselves. CI runs only when workflow files change, so it stays out of
your project's CI. Run locally:

```sh
.lean/scripts/check-structure.sh   # referenced paths, dead paths, settings, markers, exec bits
.lean/tests/test-mode.sh           # the workflow mode config
.lean/tests/test-tracker.sh        # tracking records
.lean/tests/test-hooks.sh          # Quality Gate and SessionStart hooks
.lean/tests/test-queue.sh          # the full mode queue and its claim protocol
```

## What to delete after copying

These belong to this template, not to your project:

- `.lean/scripts/`, `.lean/tests/`, and `.github/workflows/lean-workflow.yml` — self-checks for
  the workflow files themselves. **If you delete these, clear the Quality Gate block in
  `.lean/PROJECT.md` in the same go, or run `/lean-init` to refill it from your project.** The
  block ships naming those scripts, so leaving it is a `Stop` hook that fails on every turn,
  and `CLAUDE.md` tells the agent not to repair a failure it did not cause — it will report
  `BLOCKED` instead, every time.

Keep `.lean/bin/`. It is not a self-check: `mode.sh` is read by the `SessionStart` hook on every
session, and `queue.sh` is the `full` mode queue.
- `CONTRIBUTING.md` — how to contribute to this template.
- This `README.md` — replace it with your own. The workflow's description lives in `.lean/README.md`.

Keep `.github/pull_request_template.md`. It is the Result Contract, which is the format Lean
Workflow asks every change to report in.

## Upgrading

See `.lean/CHANGELOG.md`. Read the entry for the version you are moving to before you start: a
MAJOR entry carries migration steps that must run before the replace steps.
