# Eval run artifacts

One JSON file per run, schema `lean-measure/1`, consumed by `evals/measure.py report`.
Create them from a `run_evals.py` result with `measure.py extract` (no model calls).

Fields (all required; unknown fields are dropped):

- `schema`: `"lean-measure/1"`; `synthetic`: true for demo/test data (shown as `[SYNTHETIC]`)
- `case`, `run`: case name and run number
- `arm`: `{name, kind}`; `kind` is `template` (the distributed template changed) or
  `local-settings` (project-local settings changed). Arms of different kinds never merge.
- `meta`: `provider`, `model`, `runtime` (CLI version label), `revision` (Lean revision measured).
  Within one arm these must be identical; otherwise `report` refuses unless `--group-by` splits them.
- `outcome`: `correct`, `false_success` (graders failed but the agent claimed completion),
  `incorrect` (failed, no claim or claim unknown), `blocked` (harness/runtime failure or timeout)
- `tokens`, `cost_usd`, `seconds`, `tool_turns`, `user_exchanges`: numbers or null. `cost_usd` is
  only what the runtime reported; prices are never assumed. For Claude, `tokens` sums input, output
  and cache tokens from the result usage; Codex reports input plus output.
  `user_exchanges` is the task prompt plus any AskUserQuestion calls. `tool_turns` and
  `user_exchanges` need the raw `<case>#<n>.jsonl` next to `report.json`; otherwise they are null.

Sanitization: `extract` copies only the fields above. Prompts, agent text, tool inputs, failure
messages, file paths, fixture directories and changed-file lists are never written; case, arm and
metadata strings must match `[A-Za-z0-9][A-Za-z0-9._+-]{0,79}` so paths and free text are rejected.

The `synthetic-*.json` files here are invented demonstration data. They are not measurements and
do not reproduce the historical changelog figures.

    python3 evals/measure.py report evals/measurements
    python3 evals/measure.py extract <results-dir>/report.json --out <dir> --arm template-4.4.0 \
        --arm-kind template --runtime claude-x.y.z --revision abc1234
