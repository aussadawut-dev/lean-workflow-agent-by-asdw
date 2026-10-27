# Model and effort eval, round 1 (2026-10-27)

One headless agent run per model and effort on the same small coding task, scored by hidden tests, wall time and
tokens. Subscription logins only (API keys removed). Stopped after round 1 at the user's 3M-token cap (about 2.3M
spent, pilots included); agy got one pilot and round 2 (harder tasks) did not run. Tracker: `docs/tracking/TCK008.md`.

## Method

- Task (`task/`): implement `apply_patch(original, patch)` for a single-file unified diff (README rules: headers,
  omitted counts, zero-count starts, `\ No newline at end of file`, count checks, offset search, errors).
  A fresh Git copy per run; the agent may run the visible test. Prompt: "Read README.md and complete the task ..."
- Grading (`grade.py`, `hidden/`): 30 hidden subtests (23 cases, 7 errors), validated first: the reference
  (`reference/`) scores 30/30, the stub 0/30. The README was clarified once after the pilot (a malformed `@@` line
  raises `ValueError`), before round 1.
- Runner (`harness.py`, `round1.json`): the `models.json` command shapes; Codex `exec --sandbox workspace-write`,
  Claude `-p --permission-mode acceptEdits --allowedTools "Bash(python3 -m unittest:*)"`, agy `-p` with temporary
  allow rules (read-only commands, `python3`, `git`, and writes only under the runs folder; restored afterwards).
  At most 2 runs per provider at once, 900 s limit. `harness.py` imports `lean.spawn` by an absolute path; adjust it
  to rerun.
- Tokens: Claude and agy = input + cache writes + output (cache reads logged apart); Codex = its "tokens used"
  total. Not comparable across providers; times are.

## Round 1 results (30 hidden subtests)

| Model | low | medium | high | xhigh | max | ultra |
|---|---|---|---|---|---|---|
| gpt-6.1-terra | 30 · 38 s | 30 · 68 s | 30 · 41 s | 30 · 103 s | 30 · 234 s | 30 · 131 s |
| gpt-6.1-sol | 30 · 49 s | 30 · 107 s | 30 · 193 s | 30 · 286 s | 30 · 288 s | 30 · 343 s |
| gpt-6-astra | 30 · 80 s | 30 · 93 s | 30 · 132 s | 30 · 274 s | 30 · 453 s | 30 · 338 s |
| gpt-6-luna | 29 · 34 s | 29 · 40 s | 28 · 83 s | 30 · 112 s | 30 · 164 s | — |
| claude-haiku-5-5 | 30 · 70 s | 30 · 81 s | 30 · 140 s | 30 · 160 s | 30 · 491 s | — |
| claude-sonnet-5-5 | 30 · 29 s | 30 · 47 s | 30 · 62 s | 30 · 175 s | 30 · 770 s | — |
| claude-opus-5-5 | 30 · 33 s | 30 · 65 s | 30 · 89 s | 30 · 285 s | 30 · timeout 900 s | — |
| claude-fable-5-1 | 30 · 109 s | 30 · 190 s | 30 · 234 s | 30 · 472 s | 30 · 515 s | — |
| gemini-3.8-flash-low (agy pilot) | 30 · 53 s | | | | | |

Tokens per run are in `results/round1.jsonl`. `results/probe.jsonl` is an earlier SemVer task that every probe
passed (too easy); `results/pilot*.jsonl` are pilots.

## Reading

- Correctness saturated: 42 of 43 round-1 runs scored 30/30; only `gpt-6-luna` lost subtests below `xhigh`. This
  task does not separate the stronger models; it separates speed and token use.
- Higher effort bought nothing here and cost a lot: `max` took 4-13x the `low` time (Opus `max` hit the 900 s limit),
  and Sonnet/Haiku `max` used about 220k processed tokens.
- Fastest at 30/30: Sonnet low (29 s), Opus low (33 s), Terra low (38 s), Terra high (41 s), Sol low (49 s).
  Terra was faster than Sol at every effort with the same score.
- Haiku was not faster than Sonnet or Opus at low effort here and used more tokens.

## Limits

One task, one run per setting, one machine; run-to-run variance is not measured. A small, well-specified task: it
cannot show where higher capability or effort pays off (ambiguous, multi-file or long work). agy was piloted once.
