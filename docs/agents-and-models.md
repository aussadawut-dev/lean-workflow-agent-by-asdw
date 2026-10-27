# Agents and models

[Back to README](../README.md)

Policy: [.lean/policy/MODELS.md](../.lean/policy/MODELS.md). Procedure: [lean-agents](../.lean/skills/lean-agents/SKILL.md).

## The model list

`.lean/models.json` is yours to edit:

```json
{
  "schema": 1,
  "max_agents": 1,
  "default_provider": "claude",
  "providers": {
    "claude": {"command": "claude", "args": ["-p", "{prompt}", "--model", "{model}", "..."],
               "tiers": {"S": {"model": "claude-sonnet-5-5", "effort": "low"}, "M": {"...": "..."}}}
  }
}
```

Sizes, smallest first: `3S` locate or a one-line change, `2S` small mechanical work, `S` a small well-specified task, `M` normal implementation or review, `L` hard reasoning, `XL` large or entangled work, `2XL` work an `XL` attempt could not do, `3XL` the last resort. `S`, `M`, `L` and `XL` are required per provider; the others are optional, and a size a provider does not define is refused, not replaced. `lean models` prints the list; `lean models check --live` asks Codex's model cache and `agy models` which IDs exist (Claude cannot list models; its IDs are confirmed when a spawn uses them). An unavailable model is reported, never replaced silently.

## Three levels

| Level | Trigger | How many at once |
|---|---|---|
| default | no `/lean-agents` | at most `max_agents` (1), sized; only when cheaper than finishing in the session |
| max | `/lean-agents` | one per task that can run in parallel |
| explicit | `/lean-agents <model> xN` | up to N on that model; fewer when fewer tasks are independent, with the reason |

## Plan and run

Describe the work as tasks that each own their files:

```json
{"tasks": [
  {"id": "api", "files": ["src/api.py", "tests/test_api.py"], "size": "M", "deps": [], "prompt": "..."},
  {"id": "ui", "files": ["web/items.js"], "size": "S", "deps": ["api"], "prompt": "..."}
]}
```

```sh
python3 .lean/bin/lean spawn plan --tasks tasks.json                    # default level
python3 .lean/bin/lean spawn plan --tasks tasks.json --level max        # /lean-agents
python3 .lean/bin/lean spawn plan --tasks tasks.json --model sonnet -n 3 # /lean-agents sonnet x3
python3 .lean/bin/lean spawn run --tasks tasks.json --level max --provider codex
python3 .lean/bin/lean spawn clean <run-id>
```

The plan puts tasks into waves: a task waits for its dependencies, and two tasks that share a file never run together. In a session, pass each task's `model` and `effort` to the runtime's subagent tool. `spawn run` instead starts `claude -p`, `codex exec` or `agy -p` processes, each in its own git worktree from HEAD, with a progress bar per agent (`lean watch` shows them too). It refuses an uncommitted working tree unless `--allow-dirty`, and it integrates nothing: the Controller reviews each worktree's diff and applies it.

## Permissions in headless runs

A headless agent cannot ask you for permission, so it gets only what its provider settings already allow; the default `args` in `models.json` grant nothing extra. An agent that changed nothing ends as `no-changes`, not `done`, and the summary names any tool its provider reported denying.

- **Claude** (`--permission-mode acceptEdits`): may edit files; shell commands such as test runs need allow rules in the project's `.claude/settings.json` (for example `"Bash(python3 -m unittest:*)"`).
- **Codex** (`--sandbox workspace-write`): may edit and run commands inside its worktree.
- **agy**: denies every tool that needs permission (verified with agy 1.4.7: `RunCommand` denied, nothing written). Add allow rules under `permissions.allow` in agy's settings (for example `command(python3)`), or add `--dangerously-skip-permissions` to the agy `args` in `models.json` only if you accept that agent running any command on this machine; its worktree isolates files in Git, not the machine.

### Opting in with `--trust-agents`

`lean spawn run --trust-agents` is the explicit, per-run opt-in. It appends each provider's `trusted_args` from `models.json` to the agent command: Claude `--permission-mode bypassPermissions` (replacing `acceptEdits`), agy `--dangerously-skip-permissions`, Codex nothing (its `workspace-write` sandbox already allows commands in the worktree). It is never the default; Lean prints a warning, marks each agent `trusted` in `status.json`, and `command.txt` shows the flags.

Risk: a trusted agent can run any command on this machine, including outside its worktree, because worktrees isolate files in Git, not the machine. Use it only for tasks and prompts you trust. The safer alternative is provider allow rules (Claude `.claude/settings.json` `permissions.allow`, agy `permissions.allow`), which grant only the commands you name and work without the flag.

## Subscription only

`spawn run` removes `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` and similar variables from each agent's environment and says which it removed, so the provider CLIs use your subscription login instead of metered API billing. It cannot change a login the CLI stored itself: a Codex `auth.json` in API-key mode, a Claude `apiKeyHelper` or Console (API) login still bills metered credit, so check each CLI is logged in with your subscription. `--allow-api-keys` keeps them, only when you ask for it. More agents still spend your subscription quota faster; agy's OAuth login also has a daily request limit.

## Checking what actually ran

Record the requested model and effort for every dispatch, and the reported model only from runtime metadata: the `model` field in a Claude subagent's transcript messages, or the command `spawn run` executed (`.agent-runtime/spawn/<run>/<task>/command.txt`). A pane banner that shows the session's default model is not evidence of what the agent ran.
