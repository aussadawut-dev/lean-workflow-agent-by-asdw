# Actual tokens: Lean 4.17.0 versus 5.8.0 on Casetodian

One real subscription-authenticated A/B pair on 2026-10-31. **This run does not establish that 5.8.0 saves subscription quota.** 4.17.0 used fewer total input and output tokens; 5.8.0 used fewer uncached input tokens. Both answers passed the same source-based rubric, 6/6.

## Actual runtime usage

| Metric | 4.17.0 | 5.8.0 | Change |
|---|---:|---:|---:|
| Input tokens, including cached input | 240,151 | 382,587 | +59.31% |
| Cached input tokens (subset of input) | 180,736 | 336,256 | +86.05% |
| Uncached input tokens (input minus cached) | 59,415 | 46,331 | -22.02% |
| Output tokens | 2,274 | 2,475 | +8.84% |
| Reasoning output tokens (subset of output) | 92 | 126 | +36.96% |
| Completed shell commands | 11 | 13 | +2 |
| Tool-result bytes, not tokens | 143,360 | 188,372 | +31.40% |
| Source-inspection grade | 6/6 | 6/6 | Same |

Tokens come directly from Codex `turn.completed.usage`, aggregated across the session's requests. These are not file-size estimates or one context-window size. Cached and reasoning counts are subsets: do not add them again. Cache-write input was zero in both sessions. Requested model/effort was `gpt-6.1-sol/medium` for both; CLI invocation confirms those requested settings, while the retained JSON event stream does not independently attest backend model routing.

The 5.8.0 session made additional contract/progress calls, read WORKFLOW plus CONTEXT policy, and returned more source text through tools. The 4.17.0 session read CONTEXT policy and made fewer calls. These are observed differences, not an isolated causal estimate of the cost of each workflow feature. Both initial instruction/project reads were similar: 11,017 versus 10,810 output bytes.

## Quota observation

The app-server `account/rateLimits/read` snapshots showed the weekly bucket at **61% used** before 4.17.0, before 5.8.0, and after 5.8.0, with the same reset timestamp. The immediate post-4.17.0 read timed out after 20 seconds and is explicitly unavailable. Unchanged displayed percentages do not mean zero quota cost: the snapshot is coarse, reporting may lag, and the Controller also used this account during the experiment. No per-arm quota consumption percentage can be attributed from this pair.

OpenAI documents that context, reasoning, tool use and caching affect subscription usage and that credit prices alone do not determine included subscription usage. Therefore a lower uncached-token count is not proof of lower quota consumption. [Official usage and pricing documentation](https://learn.chatgpt.com/docs/pricing).

## Task, controls and quality

The identical task asks whether Casetodian's Gmail OAuth/API removal covers old HTTP endpoints, secret cleanup and continued ordinary Gmail-host SMTP behavior. Inspect implementation and tests, cite paths/lines, and state evidence gaps. No product changes, tests, builds, database, application provider calls or nested agents were authorized. Both sessions completed with exit 0 and clean fixture Git status. The original application HEAD and Git status were unchanged.

Same app revision: `d2ef08cf1a84aaaf5db527ea44a62a1c811c7701`. Workflow revisions and prompt/project hashes are in [tokens.json](tokens.json). Exact task/project context and repeatable invocation are in [token_experiment.py](token_experiment.py). Application Git-tracked files were exported into `application/`; release-specific AGENTS, README, policy, skills, runtime and Codex hook files were exported into separate temporary Git repositories. Both use identical small project context and standard/direct config, with no registered target. This is a controlled investigation on real source, not an end-to-end Casetodian installation/upgrade or implementation-and-gate comparison.

Sessions ran sequentially, 4.17.0 first, using fresh ephemeral contexts, ignored user config/rules and a shared existing ChatGPT subscription login. Environment API keys were removed. No API key was provisioned. CLI version is retained in the JSON. Each had a 300-second cap and an advisory 15-tool-call budget; observed command counts were 11 and 13. The common prompt requested a response of at most 600 words; neither was truncated. Raw JSONL command output stays in ignored local `.agent-runtime/token-benchmark/`; published answer files normalize temporary links into source-path references.

Controller manually checked both answers against these six acceptance points:

1. All five method/path pairs and the status-only 404 assertions.
2. Implementation route registration plus unmatched-route fallback.
3. Exact deletion fields/prefix and absence of workspace/connector-type restriction.
4. Preserved nonmatching fields, including SMTP/API credentials, and the DB test's narrow fixture.
5. SMTP path independent of the Gmail flag, explicit `emailApi` exception, missing-password/no-fetch test.
6. Honest limits: source inspection only; no proven deployed migration, provider revocation or successful SMTP delivery.

Both [4.17.0 answer](v4.17.0-answer.md) and [5.8.0 answer](v5.8.0-answer.md) satisfy all six. Each session had one command with exit 1: 4.17.0 ended a batch with an `rg --files` README search that found no matches; 5.8.0 ended a batch with an unmatched zsh `*smtp*` glob. Both batches also returned useful preceding search output, and both agents subsequently completed the investigation. This is not a test failure or a successful test run. No application tests ran.

## Limits and interpretation

This is **one task, one pair**, with a fixed order and shared backend cache. Fresh conversations do not imply cold provider caches; the second arm may benefit from common-source caching. Model read/ batching choices also differ. The evidence supports reporting this pair's actual tokens, not generalizing a percentage saving or attributing differences solely to Lean. Broader claims require repeated counterbalanced runs and an implementation/gate workload with quality held constant.

For this particular task, the result supports the user's concern about 4.17.0: it used fewer total tokens and fewer commands. The measured improvement in 5.8.0 is limited to uncached input; actual quota savings remain unproven. Reducing unnecessary context reads and bookkeeping is a follow-up proposal, not an implemented change.

Earlier 5.5.0 CPU/RAM observations were superseded when the user narrowed the task to tokens/quota and chose 4.17.0; they are not part of this report.

## Reproduce

Requires a clean initialized Casetodian app checkout, local `v4.17.0` and `v5.8.0` tags, macOS/Python 3.14 used here, Codex CLI and ChatGPT subscription login. This command launches **two new inference sessions** and consumes subscription usage; do not rerun merely to validate report formatting.

```sh
python3 docs/benchmarks/2026-10-31/token_experiment.py \
  --app /path/to/casetodian-next-v2 \
  --output docs/benchmarks/2026-10-31/tokens.json
```

Manual grading annotations were added after execution. The runner retains raw runtime observations; grading requires the source-based review described above.
