# Performance: Lean 4.17.1 vs 5.0.0

Measured 2026-10-27 on one macOS machine (Python 3.14.3), offline, with no model calls. 4.17.1 is tag `v4.17.1` (0824b8a); 5.0.0 is `feat/refactor-v4` at 0aab3d9. These are workflow overheads, not agent task cost: they exclude model latency, conversation tokens, retries and caching.

Raw data: `hook-latency.json` (hooks, commands, floors, git calls, test suites) and `context-tokens-4.17.1.json` (tokens). Reproduce:

```sh
python3 docs/benchmarks/2026-10-27/measure_hooks.py --v4 v4.17.1 --v5 0aab3d9 --runs 20 --suite > hook-latency.json
python3 docs/benchmarks/2026-10-26/measure_context.py --v4 v4.17.1 > context-tokens-4.17.1.json
```

`measure_hooks.py` exports each ref with `git archive` into a fresh repository whose gate is the single command `true`, then runs every Claude hook command exactly as that version's `.claude/settings.json` configures it, 20 times. A timed Stop must pass silently (no refusal JSON) or the script stops. Test suites run once each on an unmodified export.

## Hook latency (median of 20, p90 in brackets)

| Hook | Runs | 4.17.1 | 5.0.0 | Change |
|---|---|---:|---:|---:|
| SessionStart | once per session | 625 ms (692) | 173 ms (183) | -72% |
| UserPromptSubmit | every prompt | 45 ms (46) | 41 ms (43) | within noise |
| PreToolUse, read | every tool call | 49 ms (50) | 42 ms (44) | -13% |
| PreToolUse, bound write | every tool call | 46 ms (50) | 42 ms (44) | within noise |
| Stop, no cache | every Stop | 732 ms (789) | 189 ms (202) | -74% |
| Stop, cached tree | every Stop | 728 ms (761) | 185 ms (199) | -75% |
| Status line | every refresh | none | 73 ms (79) | new |

Floors: Python start-up 17 ms, one `git rev-parse` 10 ms. One Stop starts 11 `git` processes in both versions. The cached and uncached Stop differ by only a few milliseconds here because the trivial gate costs almost nothing to rerun; with real checks the cache skips them.

## Commands (median of 20)

| Command | 4.17.1 | 5.0.0 | Change |
|---|---:|---:|---:|
| show mode (`workflow.py show` / `lean mode show`) | 54 ms | 75 ms | +39% |
| check records (`workflow.py check` / `lean mode check`) | 55 ms | 79 ms | +43% |
| check models (`model_catalog.py check` / `lean models check`) | 50 ms | 76 ms | +53% |

## Test suite (one run each)

| | 4.17.1 `run_tests.py --shards 6` | 5.0.0 `lean test --all` |
|---|---:|---:|
| Wall clock | 140 s, 29 files OK | 102 s, 27 files OK |

## Context tokens (`o200k_base`)

| Inventory | 4.17.1 | 5.0.0 | Change |
|---|---:|---:|---:|
| Startup (AGENTS.md + .lean/README.md) | 2,213 | 2,396 | +8.3% |
| Fixed-task read set (11 files) | 11,146 | 10,149 | -8.9% |
| Gate source (5 mapped files) | 31,806 | 31,838 | +0.1% |
| All executable source | 78,751 | 67,164 | -14.7% |
| Skill frontmatter | 1,025 | 644 | -37.2% |

The 2026-10-26 comparison used 4.17.0, whose gate source was smaller (28,732); 4.17.1 added the backported gate lock and refusal core.

## Where 5.0 is better

- Stop is 3.9x and SessionStart 3.6x faster: one Python process replaces the bash runner, lock helper and separate evidence scripts.
- A read-only tool call's guard is about 6 ms faster, near the noise floor; the write and prompt hooks differ by less than the noise.
- The full test suite ran about 27% faster in one run per side (29 vs 27 files, different runners), and `lean test --changed` runs only what a change can affect.
- Less code and fewer skills to load: executable source -15%, skill metadata -37%, fixed-task reads -9%.
- The gate lock needs no `ps`; 4.17.1 needs `/proc` or a procps `ps`.

## Where 5.0 is worse

- Startup context is 183 tokens larger (+8.3%), paid in every session: AGENTS.md grew with the progress, spawn and target rules.
- Plain commands are 21-26 ms slower than 4.17.1's scripts.
- A Stop still starts 11 `git` processes, about 110 ms of its 185 ms at the measured 10 ms each.
- The status line adds a 73 ms process per refresh.
- Real agent sessions are not measured: no evidence yet that 5.0 lowers tokens or turns per task.

## Limits

One machine and one measurement set; the suites ran once. Differences under about 5 ms are within noise. The trivial gate isolates workflow overhead; a project's own checks dominate a real Stop. Each side runs its own configured commands, so 4.17.1 includes its bash wrappers by design. The cause of the slower commands is not measured here; an import-time profile is the next step.
