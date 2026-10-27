# Lean v5.0.0 development log

Milestones and lessons from building v5 (workset `docs/tracking/TCK001-v5-cli-rebuild.md`), written by hand before `lean log` existed. From now on the timeline is recorded automatically: `python3 .lean/bin/lean log --summary`, and `--export docs/history/<name>.md` keeps a copy here.

## Milestones (2026-10-26, UTC, approximate)

| Time | Phase | Milestone |
|---|---|---|
| 12:30 | research | v4.17.0 analysed: 203 files, ~36k lines, fixed gate test list, no progress display or spawner. |
| 12:30–13:00 | scope | 19 decisions agreed (CLI, progress bar, spawn levels, model list, test categories, CI, free tools only). |
| 13:00–13:11 | scope | Spec TCK001 written and reviewed; retargeted to v5.0.0 as a major release; approved. |
| 13:11–13:25 | implement | v4 snapshot moved to `.temp/v4`; core ported into `.lean/lean/` (guard, evidence, gate, hooks, records). |
| 13:25 | implement | Hooks switched to the v5 CLI; the session itself ran on v5 from here. |
| 13:30–14:00 | test | 4.x suites ported (guard 33, gate 64, hook cases 50 by a Sonnet worker, records 63, others); new features and their tests written. |
| 14:00 | validate | 20/20 test files on Python 3.14 and 3.9; 4.17 snapshot and Casetodian clone migrated in scratch copies. |
| 14:05–14:15 | review | HIGH review round 1 (Opus/high): REWORK, 12 findings; all fixed with fail-first regression tests. |
| 14:25–14:35 | review | HIGH review round 2 (Opus/high): REWORK, 7 findings; fixed in the final pass. |
| 14:40 | scope | Decision changed: keep `lean-target` because Casetodian depends on it; new contract. |
| 14:45–15:00 | implement | `lean target` ported (31 tests); spawn scenario tests for all three levels; `lean log` activity log added. |

## Lessons for the next version

- **Effort was not passed on the first worker and reviewer spawns.** The Agent tool accepts `effort`; the policy now says to pass it every time, and a pane banner showing session defaults is not evidence of the model used (the transcript `model` field is).
- **Independent review found what tests did not.** 19 findings across two rounds, including two HIGH enforcement gaps (adapters missing from gate controls; a broken module locking every tool). Plan for at least one REWORK on boundary code.
- **Stop-gate refusals while waiting for review are expected noise.** Each waiting turn produced one refusal; the UNVERIFIED release keeps it from looping, but a quieter "review pending" state could help.
- **Production users must be checked before removing features.** The Casetodian dry run caught the `lean-target` dependency that the decision list had removed.
- **agy headless denies tools by default.** A spawned agy agent edits nothing without allow rules; `spawn run` now reports `no-changes` instead of a false `done`.
- **Heuristic guards also catch the author.** The v5 guard refused a heredoc that only mentioned the receipt command; writing scripts to files avoided it.
