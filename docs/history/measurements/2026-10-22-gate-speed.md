# Gate speed and downstream token baseline (2026-10-22)

Evidence behind the Unreleased entry in `.lean/CHANGELOG.md`. Wall times come from one developer machine under its usual background load, so compare them only with runs made the same way.

## Setup

- Machine: Apple M3 with 8 cores (4 performance, 4 efficiency), macOS (Darwin 27.0.0). Other developer tools kept running; the 1-minute load average at the start of each timed run is listed below. It lags, so a run that follows a parallel run starts with a higher figure.
- Tools: Python 3.14.3, Bash 3.2.57, ShellCheck 0.11.0, Git 2.50.1.
- Before: 4.12.0 (`7039cc9`). After: the same commit with this change applied.
- Each version ran in its own fresh local clone, so both recorded their gate controls on first use.
- Method: `bash .lean/scripts/quality-gate.sh --root .`, the direct runner, which runs every gate command in `.lean/PROJECT.md`. One unrecorded warm-up pair ran first, then three pairs, each running before and then after, so drifting background load falls on both versions.

## Quality Gate wall time

| Pair | Before (s) | After (s) | After / before | Load at start, before / after |
|---|---:|---:|---:|---|
| 1 | 197.5 | 40.3 | 0.20 | 20.9 / 10.3 |
| 2 | 150.7 | 40.3 | 0.27 | 27.4 / 6.8 |
| 3 | 195.1 | 48.2 | 0.25 | 21.8 / 14.0 |
| Median | 195.1 | 40.3 | 0.21 | |

Median wall time fell by 79.3%. Against the 141.0 s sequential median measured earlier the same day under lighter load, the after median is 71.4% lower.

## Per-command time

Single runs of each gate line. Before run A came early in the day and before run B shortly ahead of the timed pairs, under different background load; the after run followed the pairs.

| Gate command | Before, run A (s) | Before, run B (s) | After (s) |
|---|---:|---:|---:|
| `shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh` | 0.55 | 0.62 | 0.82 |
| `.lean/scripts/check-structure.sh` | 0.85 | 0.22 | 0.37 |
| `.lean/tests/test-hooks.sh` | 66.66 | 78.83 | in the pool line |
| `python3 .lean/scripts/workflow.py --root . check` | 0.15 | 0.07 | 0.08 |
| `python3 .lean/scripts/model_catalog.py --root . check` | 0.11 | 0.06 | 0.07 |
| `python3 -m unittest discover -s .lean/tests -p 'test_gate_integrity.py'` | 78.35 | 94.98 | in the pool line |
| `python3 -m unittest discover -s .lean/tests -p 'test_skill_pack.py'` | 1.01 | 1.09 | 1.70 |
| `python3 -m unittest discover -s tools -p 'test_*.py'` | 0.74 | 0.86 | 1.75 |
| `python3 tools/check_commit_attribution.py --root .` | 0.06 | 0.08 | 0.10 |
| `python3 .lean/tests/run_tests.py --shards 6 test-hooks.sh test_gate_integrity.py` | - | - | 43.19 |
| Sum | 148.47 | 176.80 | 48.07 |

The hook suite alone, run back to back in the same load window: 83.4 s before and 33.8 s after, with the same 110 `ok` lines in the same order.

## Stop after a passing run

Measured later the same day in a scratch clone holding the pass-reuse change. Each sample edits an untracked file, runs `bash .lean/scripts/quality-gate.sh --root . --cache-tree`, then runs the Stop command exactly as `.claude/settings.json` or `.codex/hooks.json` configures it. The comparison runs the direct gate without `--cache-tree`, which records nothing, as every direct run did before this change.

| Stop | Runs (s) | Median (s) |
|---|---|---:|
| Claude, after a `--cache-tree` pass on the same state | 0.50, 0.59, 0.53 | 0.53 |
| Codex, after a `--cache-tree` pass on the same state | 0.46, 0.56 | 0.51 |
| Claude, with no recorded pass | 51.54, 49.05 | 50.3 |

The direct `--cache-tree` runs themselves took 42.2 to 47.0 s (median 43.8 s). A `/lean-gate` run followed by a Stop on the unchanged state therefore takes about 44 s instead of about 94 s.

## Measured during analysis, not shipped

Running every gate command at once, without splitting the two suites, took a median of 81.8 s against 141.0 s for the sequential gate (three runs each, earlier the same day). Splitting the suites and running every command at once took 39.5 s. A runner that runs independent gate lines concurrently would need protected runner changes and is left for later.

## Downstream token baseline (before the wording changes)

A downstream workspace project that runs Lean in `full` mode (its Lean version changed during the period): 41 Claude Code sessions from October 2026, aggregated locally from the transcripts' API `usage` fields. No prompt, message or file content was kept. Figures describe this one project's workload; they are the baseline for a later comparison, not a measured saving.

| Measure | Value |
|---|---|
| Main-thread API calls | 4,634 |
| Main-thread tokens | 1,229.7M, of which 98.7% cache reads |
| Average context per call | 265k tokens |
| Sessions with 200 or more calls | 10 of 36: 71.5% of tokens, 311k average context (89k in sessions under 50 calls) |
| Subagent tokens | 257.9M, all on Sonnet or Haiku |
| `contract_guard.py declare` calls in the main thread | 163: 75 later in a turn whose written contract line the guard could already bind; 70 as the turn's first tool call right after the line, before the guard may have seen it; 18 with no contract line |
| Context re-sent by those calls | 12.4M tokens for the 75 later ones, 33.9M for all 163 |
| Main-thread reads of files Claude had already loaded | `AGENTS.md` 78, `.lean/README.md` 27, `CLAUDE.md` 19 |

Where the re-sent context came from, by the carried volume of each item (its tokens times the later calls in its session): the model's own earlier output 34 to 41%, the first call's prefix (system prompt, tools and instructions) 21 to 26%, files printed with `cat`/`sed` 10 to 15%, Lean CLI output 3 to 4%. The ranges are with and without the correction below.

Two checks behind those shares:

- Per-call context growth fits 0.99 × the previous call's output tokens plus 1.72 × the added tool-result characters divided by four, so earlier output, thinking included, stays in context, and characters divided by four undercounts tool results.
- After gaps of 5 to 60 minutes, 2 of 126 calls rewrote the cache; after gaps over an hour, 7 of 7 did. The cache lives about an hour, so a gate run shorter than that does not add cache writes: gate speed saves wall time, not tokens.

To compare later sessions, count per session the `declare` calls that are not a human turn's first tool call and come after an assistant text in that turn began with `Contract:`, and the `Read` or `cat`/`sed`/`head`/`tail`/`grep` calls naming `AGENTS.md`, `CLAUDE.md` or `.lean/README.md`.
