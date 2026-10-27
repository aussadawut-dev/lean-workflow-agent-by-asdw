# Models, effort and spawning

Model reasoning effort is separate from procedure intensity under `SKILL-EFFORT.md`; never translate standard/high/ultra procedure levels into runtime settings.

## Model list

`.lean/models.json` (project-owned) maps sizes to concrete models per provider (`claude`, `codex`, `agy`), with the CLI arguments `lean spawn run` uses. `lean models` prints it; `lean models check --live` asks the provider CLIs which models exist (Codex's model cache, `agy models`; Claude has no listing, so its IDs stay unverified until used). An unavailable model is reported, never silently substituted; update the list instead.

| Size | Work | Starting effort |
|---|---|---|
| `3S` | Locate, read or a one-line mechanical change | Low |
| `2S` | Small mechanical work with an exact spec (rename, format) | Low to medium |
| `S` | A small, well-specified task | Low to medium |
| `M` | Normal implementation or focused review | Medium |
| `L` | Hard reasoning, conflicting evidence, complex security/data boundaries | High |
| `XL` | Large or entangled work | High or above |
| `2XL` | Work an `XL` attempt demonstrably could not do | High or above |
| `3XL` | Last resort after `2XL`; slowest and most expensive | Highest |

`S`, `M`, `L` and `XL` are required for every provider; `3S`, `2S`, `2XL` and `3XL` are optional, so a list written for 5.0 keeps working. A size the provider does not define is refused with a message, never replaced by another (an explicit `--model` still runs). The shipped list follows the 2026-10-27 eval (`docs/benchmarks/2026-10-27-models/`): higher effort did not raise correctness on a well-specified task and cost 4-13x the time, so start low and raise one step only after a demonstrated reasoning limit.

Size each spawned task, reviewers included, by this table. Repository mode does not change model selection. Risk and quality set the required work and review depth; budget guides optional spend (`CHEAP` favors smaller sizes, `EXPENSIVE` allows justified larger ones). None removes tests, validation or required review; report an unmet floor rather than lowering it.

## Spawn levels

1. **Default (no `/lean-agents`)** — at most `max_agents` agents at once (`.lean/models.json`, default `1`), each sized to its task. Spawn only when required (delegated execution, HIGH independent review, an explicit user request) or cheaper: compare finishing in this session (context already loaded) with a spawn (brief, cold re-reads, the agent's own work, the handoff). Finish here when that costs less or about the same; size `S` work usually does. If this session's reasoning falls short on a task, spawn the next larger size and record why.
2. **`/lean-agents`** — split the work into independent tasks with exclusive file ownership and spawn one agent per task that can run in parallel; dependencies and shared files serialize tasks into later waves. `lean spawn plan --level max` computes the waves and shows the agent count before any spawn.
3. **`/lean-agents <model> xN`** — up to N agents at once, all on the named model (sizes do not apply); further tasks run in later waves. With fewer independent tasks than N, spawn only as many as can run in parallel and say so. Natural-language requests ("use 3 sonnet") mean the same.

`max_agents` caps only the default level; the user's explicit command sets the other two. Every agent spends the user's subscription quota, so more agents exhaust it faster.

## How to spawn

- **In this session** (preferred): the runtime's subagent tool. Claude's Agent tool takes `model` and `effort`; Codex's `spawn_agent` takes model and reasoning effort and needs `fork_turns: "none"` to override them (send a self-contained brief). Pass both values from the plan on every spawn, even when they match the parent; omitted settings inherit the session defaults, which are often heavier than the task needs.
- **As separate processes**: `lean spawn run --tasks tasks.json` (or `--plan plan.json`) starts headless `claude -p`, `codex exec` or `agy -p` processes, one git worktree each, shows one progress bar per agent and leaves each worktree for the Controller to integrate. It removes metered API credentials (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` and similar) from each child so the provider CLI uses the subscription login; `--allow-api-keys` keeps them only on the user's explicit request. Logins a CLI stored itself (a Codex API-key `auth.json`, a Claude `apiKeyHelper` or Console login) are outside its reach and still bill metered credit. Commit or pass `--allow-dirty` first: worktrees start from HEAD.

The task list is JSON: `{"tasks": [{"id": "api", "files": ["src/api.py"], "size": "M", "deps": [], "prompt": "..."}]}`.

## Records

Record every dispatch before the call: the requested model and effort, context mode (fresh or full-history, with reason), the size/level that chose them, and the agent identity. Never use bare `inherited/inherited`; when the tool cannot set a value, record the known parent/default and the limitation, or `unavailable`. Report backend settings only from runtime metadata (for Claude, the `model` field of the subagent's transcript messages; for `lean spawn run`, the command it ran); a pane header or banner that shows the session's defaults is not evidence of the agent's model. Do not store credentials, raw prompts or price assumptions.

## Independent review

`HIGH` review uses an independent context with the Task Contract and diff, without author reasoning, under `REVIEW.md`. Choose the smallest capable reviewer size; a stronger model is not required. A wording-only diff (instruction or documentation prose that adds or removes no rule and leaves normative keywords, numbers, paths, commands, code and structure unchanged) may use size `S` with a before/after rule map the reviewer checks against the text; any change to code, tests, hooks or configuration uses the normal size. This lowers reviewer cost only; the HIGH floor, independence, receipt and round limits stay unchanged.

## Runtime control

- The active session's own model and effort stay with the user; never claim to have changed them, or a subagent's settings, unless the runtime confirms it.
- If a desired model is unavailable, use a capable available option from the list. If none can meet the floor, report `BLOCKED` with the limitation.
- Classify failure first: fix implementation, context, tools or permissions at their source. For a demonstrated reasoning limit, raise one effort level, then one size; change one variable per retry, record why and obey `REVIEW.md`'s round cap. Task length alone does not justify escalation; budget never lowers quality.
