# Quality Gate, hooks and progress

[Back to README](../README.md)

## The gate

`python3 .lean/bin/lean gate run` runs the commands between the gate markers in `.lean/PROJECT.md`, with a bar per check, under a per-checkout lock. It also checks the Task Contract, the review receipt a HIGH contract or a High-risk change needs, and drift in the gate's own controls. Policy: [.lean/policy/QUALITY.md](../.lean/policy/QUALITY.md).

```sh
python3 .lean/bin/lean gate run --cache-tree                       # reuse a pass for an unchanged state
python3 .lean/bin/lean gate run --require-review --contract '...'  # validation plus receipt check
python3 .lean/bin/lean gate status                                 # last recorded result, no run
python3 .lean/bin/lean gate mode auto_fixloop                      # auto | manual | auto_fixloop | manual_fixloop
```

A gate command written as `python3 .lean/bin/lean gate scope -- <command>` is skipped when the change touches only work records (trackers and queue items), so bookkeeping does not rerun application suites; `--only`/`--always` adjust the paths and `LEAN_GATE_SCOPE=full` runs everything. A batch of tasks gets one full gate, and a suspected flaky failure at most 2 reruns ([QUALITY.md](../.lean/policy/QUALITY.md#change-scoped-checks-batches-and-flaky-failures)).

## Hooks per provider

| Event | Claude (`.claude/settings.json`) | Codex (`.codex/hooks.json`, after trust) | agy |
|---|---|---|---|
| Session start | records a change baseline, prints policy and onboarding notes | same, as additional context | — |
| Prompt | a person's prompt clears the declared contract | same | — |
| Before a tool | contract guard: writes wait for a contract | same | — |
| Stop | gate run; refusal blocks with a reason | gate run; refusal blocks with a reason | run `lean gate run` yourself |
| Status line | `lean status --line` | built-in items only | — |

Every hook is `lean hook <provider> <event>`; the logic is shared, only input and output formats differ. A repeated, unchanged refusal is released UNVERIFIED instead of looping, and three continued refusals release the Stop so the agent can report BLOCKED; a release is never a pass.

## Review receipts

The independent reviewer captures `lean evidence state`, reviews, and records `lean evidence record-review --contract '<exact line>' --reviewer '<id>' --state '<captured>' --verdict PASS|REWORK --evidence '<scope>'`. The guard refuses that call from the author's own session. Any later content change invalidates the receipt; staging or committing the whole reviewed change keeps it. Tracker files directly under `docs/tracking/` are excluded so the result can be recorded after review.

## Protected controls

The gate records its controls on first use (hook configuration, the gate mode file, the `lean` entry, every module in `.lean/lean/`, the gate block) and refuses changes until they are accepted: by an independent HIGH review that covers them, by matching a trusted remote ref listed in PROJECT.md, or by `lean gate accept-controls --reason '<user approval>'`.

## Progress surfaces

Progress written by `lean progress set` is kept per session in `.agent-runtime/progress/<session>.json` (session from `LEAN_SESSION_ID`, `CLAUDE_CODE_SESSION_ID` or `CODEX_THREAD_ID`; files untouched for 7 days are pruned), and `.agent-runtime/progress.json` holds the latest update of any session. A surface that knows its session (the Claude status line from its stdin, hooks from their payload, commands from the environment) shows its own bar, and another session's only labelled `session <id>:`, so concurrent sessions in one checkout do not mistake each other's progress for their own. It drives: the agent's replies, `lean status`, `lean watch`, `lean test`, `lean gate run`, `lean spawn run` (a bar per agent, read from each agent's own worktree), the Claude status line, Claude's Stop message after a pass and Codex's Stop message. Gap: Codex and agy cannot draw a custom line in their own window; use `lean watch` beside them.
