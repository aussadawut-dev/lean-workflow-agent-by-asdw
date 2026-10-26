# TCK001 — Lean v5.0.0: rebuild as a single `lean` CLI

Status: DONE
Owner: Controller (active session)
Risk: HIGH · Quality: VERY_HIGH · Mode: tracker/direct
Scope level: standard

## Goal

Rebuild Lean from scratch on branch `feat/refactor-v4` as major release v5.0.0 (breaking: removed
skills, new CLI paths, new hook entries, new test layout, new spawn defaults) in one proportional `lean` CLI. Keep the
Lean concept (contract, tests, validation, review, gate; modes standard/tracker/full; direct/delegated).
Add visible progress, impact-based test selection, and model-sized agent spawning for Claude, Codex
and agy. Everything runs on free tools; spend only the user's existing subscription quotas.

## In scope

1. **Reset.** Move all current tracked workflow files to `.temp/` (git-ignored) as read-only reference.
   Rebuild from an empty layout. Git history stays the source of truth for the old version.
2. **Single CLI.** `.lean/bin/lean` entry, logic in `.lean/lean/` modules (Python 3.9+ stdlib, argparse).
   Subcommands (names final at implementation, behavior fixed here):
   `status`, `watch`, `contract`, `test`, `gate`, `models`, `spawn plan`, `spawn run`, `mode`
   (configure/show/check/tracker/queue), `hook <event>`, `update`.
   Claude and Codex hooks call `lean hook ...` only.
3. **Port the core** (before new features): contract guard, gate (mode auto/manual/fixloop, lock,
   evidence/review receipts, cache), modes + tracker + full-mode queue leases, skill effort, structure
   check, commit-attribution check, `lean-update`. Port by capability inventory (TASK-02), not by file.
4. **Skills.** Keep 9 core skills (init, task, scope, research, grill, agents, review, gate, effort) plus
   `lean-update`. Remove the other 8 optional skills and their tools/tests: audit, catalog, compress,
   pattern, playbook, prune, takeover, target. Remove the optional skill-pack mechanism.
5. **Progress display.** Solid/shade bar, 20 cells, 5% per cell: `████████░░░░░░░░░░░░ 40%`.
   Percent = lean-task phase (contract → scope → implement → test → validate → review → gate), refined
   by sub-progress (items/tests) inside the current phase. One state file feeds every surface:
   - agent prints the bar in its reply on each phase change (AGENTS.md rule; all providers);
   - `lean test`, `lean gate`, `lean spawn run` (one bar per agent);
   - Claude statusLine;
   - `lean watch` live view in a separate pane (Codex/agy way to see a live bar);
   - Codex Stop hook `systemMessage` (when Codex trusts hooks).
   Documented parity gap: Codex and agy have no custom in-window status line.
6. **Models.** Config holds a model list per provider (claude/codex/agy) with tiers S/M/L/XL mapping to
   concrete model IDs and effort. `lean models` lists them and checks availability where the provider
   CLI allows. No hard-coded provider IDs in policy prose.
7. **Spawning.**
   - Default `max_agents=1`: spawning works without invoking `/lean-agents`, one agent at a time,
     sized S/M/L/XL to the work. If spawning costs more than finishing in the main session, the main
     session does the work. If the main session's reasoning is insufficient, escalate to a larger tier
     with a recorded reason (replaces the old premium-evidence wording).
   - `/lean-agents` (no arguments): spawn as many agents as the work splits into independent tasks
     with exclusive file ownership (maximum parallelism), each sized S/M/L/XL. Only the runtime's own
     limit caps it; the plan shows the agent count before dispatch.
   - `/lean-agents <model> xN` (e.g. `/lean-agents sonnet x3`): exactly N agents on that model,
     overriding tier sizing. Fewer independent tasks than N: spawn only as many as can run in parallel
     and say so. CLI equivalent: `lean spawn run --model <id> -n N`.
   - Natural-language requests ("use 3 sonnet") translate to the structured form.
   - `lean spawn plan`: JSON batches (task, files owned, tier, model, effort) for in-session spawning.
   - `lean spawn run`: real headless processes — `claude -p --model`, `codex exec -m`,
     `agy -p --model --print-timeout` — each in its own git worktree, results collected back.
   - Subscription-only guard: strip `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/Gemini API keys from child
     env, warn, continue. Explicit override flag to keep them.
8. **Tests by category.** `tests/unit`, `tests/hooks`, `tests/e2e`, plus an impact map (path glob →
   categories/files). `lean test --changed` runs only tests the diff affects; docs-only diffs run lint
   only. Full suite runs at release and in CI (GitHub Actions workflow added).
9. **Docs.** Rewrite README and guides for the new CLI; keep `docs/benchmarks/`, `docs/history/`,
   `evals/` as history (not ported, not in gate). CHANGELOG 5.0.0 entry with a "Migrating from 4.x"
   section listing every changed path, command, hook entry and removed skill.

## Out of scope

- Paid services, third-party Python packages, network services.
- Auto-parallel spawning by default.
- Porting the 8 removed optional skills.
- Native Windows.

## Acceptance criteria

- [x] AC-01: Old files live under git-ignored `.temp/`; tracked tree contains only the new layout.
- [x] AC-02: `.lean/bin/lean --help` lists every subcommand above; no workflow script lives outside `.lean/lean/`.
- [x] AC-03: Capability inventory (TASK-02) has every kept capability mapped to a passing test; every dropped one marked with reason.
- [x] AC-04: Contract guard denies an undeclared write and allows it after a contract, in Claude and Codex hook tests.
- [x] AC-05: Gate runs in auto/manual/fixloop modes with lock and review receipts; regression tests from the old suite that cover kept behavior pass.
- [x] AC-06: Progress bar renders `████████░░░░░░░░░░░░ 40%` from one state file in `lean status`, `lean watch`, `lean test`, `lean gate` and Claude statusLine; Codex Stop hook emits it.
- [x] AC-07: `lean models` prints S/M/L/XL per provider from config; unknown/unavailable models are reported, not substituted.
- [x] AC-08: Without `/lean-agents`, `lean spawn plan` emits ≤ `max_agents` (default 1) concurrent agents; `/lean-agents` mode emits one agent per independent task (5 independent tasks → 5); `--model X -n 3` emits 3 agents on X, or fewer with a stated reason when fewer tasks are independent; file ownership is always disjoint.
- [x] AC-09: `lean spawn run` launches claude/codex/agy in separate worktrees with the chosen model, strips API keys (test asserts child env), shows per-agent bars, enforces timeout; agy no-TTY hang check recorded.
- [x] AC-10: `lean test --changed` runs only mapped categories; a docs-only diff runs lint only; `lean test --all` runs everything.
- [x] AC-11: CI workflow runs lint + full suite on push/PR.
- [x] AC-12: Only free tools used: stdlib-only import check passes.
- [x] AC-13: `lean-update` upgrades a real 4.17.0 install to 5.0.0 in a temp repo, migrating hooks, gate block and config automatically; project-owned files preserved.
- [x] AC-15: Migration dry run on a temporary copy of a production 4.x user repo (Casetodian) reports every change and leaves the original untouched.
- [x] AC-16: `lean target` keeps 4.x target behavior; the 31 ported submodule tests pass.
- [x] AC-17: Scenario tests run each spawn command through `lean spawn run` with stub providers and verify concurrency, models, effort and provider flags.
- [x] AC-18: `lean log` shows a timeline and per-phase summary of recorded events and exports them; `docs/history/v5-development-log.md` records this build.
- [x] AC-14: Full suite + gate pass; HIGH independent review PASS.

## Tasks

- [x] TASK-01: Reset — move tracked files to `.temp/`, add ignore, scaffold layout.
- [x] TASK-02: Capability inventory of old v4 (from `.temp/`): keep/drop list with reasons.
- [x] TASK-03: CLI core + config + mode/tracker/queue.
- [x] TASK-04: Contract guard + hooks (Claude, Codex) via `lean hook`.
- [x] TASK-05: Gate (modes, lock, evidence, cache) + structure + attribution checks.
- [x] TASK-06: Test categories, impact map, `lean test`, CI workflow.
- [x] TASK-07: Progress state + bar + `status`/`watch`/statusLine/Codex hook.
- [x] TASK-08: Models config + `lean models`.
- [x] TASK-09: `spawn plan` + spawning rules in AGENTS.md / lean-agents / MODELS policy.
- [x] TASK-10: `spawn run` adapters (claude/codex/agy), worktrees, key guard.
- [x] TASK-11: Skills (9 core + lean-update) and policy rewrite, proportional and shorter.
- [x] TASK-12: `lean-update` port.
- [x] TASK-13: Docs, CHANGELOG 5.0.0 with 4.x migration guide, version bump to 5.0.0.
- [x] TASK-14: Full validation, gate, independent HIGH review.

## Capability inventory (TASK-02)

Kept, with the 4.x tests ported unchanged in intent (only invocations moved to the CLI):

| 4.x capability | v5 home | Tests |
|---|---|---|
| Contract parse/declare/transcript binding, write detection, receipt protection, self-repair | `lean/guard.py`, `lean contract`, `lean hook * pre-tool|prompt` | `hooks/test_guard.py` (33, from test_contract_guard) |
| Gate runner, cache, refusals/release, controls drift, trusted refs, receipts, High-risk floor | `lean/gate.py`, `lean/evidence.py`, `lean gate`, `lean evidence` | `hooks/test_gate.py` (64, from test_gate_integrity), `hooks/test_hook_cases.py` (50, from test-hooks.sh) |
| Gate mode auto/manual/fixloop | `lean gate mode`, `.lean/gate.json` | `hooks/test_gate_mode.py` (19) |
| Gate lock | `lean/gate.py` | `hooks/test_gate_lock.py` (6) |
| Claude/Codex adapters | `lean/hooks.py` | the three suites above |
| Modes, trackers, queue leases, downgrade, context, tracker archive | `lean/records.py`, `lean mode|tracker|queue` | `unit/test_records.py` (63), `unit/test_downgrade.py` (13), `unit/test_tracker_guards.py` (5), `e2e/test_lifecycle.py` |
| Queue history reading | `lean/records.py` | `unit/test_queue_history.py` (2 of 18; the rest covered clean-queue) |
| Procedure intensity | `lean effort` | `unit/test_effort.py` (6) |
| Structure checks | `lean lint` | `unit/test_structure.py` (new, replaces test_structure/test_shared_assets) |
| Commit attribution | `lean attribution` | `unit/test_attribution.py` (from tools/) |
| Upstream update | `lean update` (own snapshot/journal, no takeover dependency) | `e2e/test_update.py` (replaces test_update_workflow) |
| Parallel test runner | `lean test` | `unit/test_testsel.py` (replaces test_run_tests) |
| Model catalog/drift | `lean models` | `unit/test_models.py` |

Kept after D22: targets (`submodule.py` -> `lean/target.py`, test_submodule -> `hooks/test_target.py`, 31 tests).

Dropped (D1/D2): takeover (`takeover.py`, test_takeover), repository cleanup (`clean_repo.py`, test_clean_repo), queue cleanup (`clean-queue`), skill pack (`skill_pack.py`, test_skill_pack), template bootstrap tests tied to the skill pack (test_template), model catalog proposals (`model_catalog.py`); evals and benchmarks kept as history outside the gate.

## Decisions

- D1 Keep `lean-update`; remove audit, catalog, compress, pattern, playbook, prune, takeover. (Revised 2026-10-26 by the user after the Casetodian dry run: keep `lean-target` as a core skill.)
- D2 Benchmarks/evals kept as history, not ported.
- D3 `.temp/` git-ignored.
- D4 CLI at `.lean/bin/lean`, modules in `.lean/lean/`.
- D5 Progress = lean-task phase + sub-progress.
- D6 Show progress everywhere (reply, test/gate/spawn, Claude statusLine, `lean watch`, Codex hook).
- D7 Parity gap accepted: Claude-only statusLine; Codex/agy use reply + `lean watch` + Codex hook.
- D8 Bar style solid/shade, 20 cells.
- D9 `max_agents=1` default; spawn without `/lean-agents`; sized S/M/L/XL; main session if cheaper; escalate tier when reasoning falls short.
- D10 `spawn run` in this round, with agy.
- D11 Model list per provider.
- D12 Structured and natural-language spawn commands. Three spawn levels (user recheck 2026-10-26):
  default (no `/lean-agents`) = D9; `/lean-agents` = maximum parallel agents the work allows;
  `/lean-agents <model> xN` = N agents on that model.
- D13 API keys stripped from child env with warning.
- D14 agy supported (1.4.7 local: `-p`, `--model`, `--output-format`, `--print-timeout` confirmed).
- D15 Test categories unit/hooks/e2e.
- D16 Full suite at release and in CI.
- D17 Docs-only diff: lint only.
- D18 Mode tracker, execution direct.
- D19 Core port before new features.
- D20 Release as v5.0.0 (major) because changes break 4.x installs; branch name stays `feat/refactor-v4` (user 2026-10-26).
- D21 `xN` in `/lean-agents <model> xN` is the agent count (user confirmed 2026-10-26).
- D22 Keep `lean-target` in v5: `lean target use|context|clear|gate`, record-root routing for mode/tracker/queue/effort/models, target gate before Lean's, target High-risk policy and gate-block controls (user 2026-10-26).
- D23 Scenario tests for the three spawn commands prove what each spawns (user 2026-10-26).
- D24 Development activity log: timed events in `.agent-runtime/activity.jsonl`, `lean log` timeline/summary/export, and a v5 development log in `docs/history/` (user 2026-10-26).
- Implementation choices within scope: the gate runner is Python (no bash/ShellCheck); gate runtime markers moved to `.agent-runtime/`; impact selection ignores paths outside the workflow `scope` so downstream application changes never run Lean's tests; `lean lint` checks references only in Markdown agents follow (workflow files, entrypoints, PROJECT.md and its routed documents); `spawn run` reports `no-changes` and names denied tools instead of `done` when an agent edited nothing.

## Risks and open points

- **Resolved by D22: Casetodian uses `lean-target`.** The AC-15 dry run on a clone of `casetodian-workspace` (4.16.0) applied cleanly and `mode check`/`models check` pass, but lint reports 6 references to the removed `submodule.py` (its AGENTS.md project additions, README, PROJECT.md), and v5 no longer routes records to `.lean/targets/casetodian-next-v2/` or runs the target's gate. Upgrading that project as-is would lose its target workflow. Options: keep `lean-target` in v5 (port submodule.py and its tests), keep Casetodian on 4.x, or restructure Casetodian before upgrading.
- agy headless denies every tool that needs permission (verified: `RunCommand` denied, nothing written); `spawn run` now reports `no-changes` with the denied tool. Granting agy permissions (allow rules or `--dangerously-skip-permissions`) is the user's choice; the shipped args grant nothing.
- Gate controls changed throughout; acceptance needs the independent HIGH review (or user-approved `accept-controls`).
- Codex hooks were not exercised in a live Codex session (adapters are covered by tests running the configured commands); agy has no hooks.
- CI on a private repo uses limited free minutes.

## Evidence

- Gate PASS 5/5 with controls accepted by HIGH review PASS (reviewer-subagent-opus-c2r3); lean test --all 25/25 on Python 3.14 and 3.9

- 2026-10-26: `workflow.py configure tracker --execution direct` → `{"mode": "tracker", "configured": true, "execution": "direct"}`.
- Research: v4 = 203 files / ~36k lines; gate runs a fixed test list; no progress or spawner exists.
- `python3 .lean/bin/lean test --all` → 20/20 test files pass on Python 3.14.3 and 3.9.6 (`/usr/bin/python3`); `lean lint` → lint ok.
- AC-13: 4.17.0 snapshot (`.temp/v4`) → `lean update preview|apply` from a scratch v5.0.0 tag: 64 delete, 2 link, 72 write; `mode check` and `models check` pass; lint flags only that template's own old docs and PROJECT.md High-risk lines naming 4.x scripts (the preview lists them as notes).
- AC-15: clone of `/Users/x10/Workspace/Product/casetodian-workspace` (original untouched: `git status --porcelain` empty): 80 delete, 72 write; custom skills (commit-push-tag, deploy-sit, gate-mode, prisma-*) kept; gate block's project lines kept; lint 6 problems, all `submodule.py`/4.x path references (see open point).
- AC-09: `agy -p ... --print-timeout 90s` with stdin closed and output captured exited 0 in 10.4s (no TTY hang on 1.4.7); `lean spawn run --provider agy` smoke ran in a worktree; agy denied `RunCommand` → reported `no-changes` after the fix.
- Bug found and fixed with a fail-first regression: `lean update preview` recorded the wrong release ref when retired skill links existed (a loop variable shadowed it); `e2e/test_update.py` asserted the ref, failed with `'lean-quality-gate-mode' != 'refs/tags/v5.0.0'`, then passed after renaming the variables.
- Dispatch TASK-port-hooks | level=default | size=M | requested model/effort=sonnet/(not passed — Agent tool effort omitted by mistake) | context=fresh | agent=general-purpose subagent | reported model=claude-sonnet-5-5 on all 12 assistant messages (subagent transcript `message.model`); result: `hooks/test_hook_cases.py`, 50 tests pass, verified by the Controller.
- Dispatch review rounds 1–2 (spec contract) | reviewer | requested sonnet | reported claude-sonnet-5-5 (transcript).
- Dispatch HIGH review round 1 (implementation contract) | reviewer | size=L | requested model/effort=opus/high | context=fresh | agent=reviewer subagent | verdict REWORK, 12 findings (2 HIGH, 4 MEDIUM, 6 LOW), all reproduced by the reviewer.
- Round 1 fixes, each with a regression test written first and shown failing before the fix:
  1. HIGH: every `.lean/lean/*.py` is now a gate control (`evidence.control_names`, also from a commit's tree); `hooks/test_controls.py` refused nothing for hooks.py/structure.py/testsel.py/update.py before, now refuses each.
  2. HIGH: `bin/lean` handles `hook <provider> pre-tool|prompt` importing only the guard; if the package cannot load, reads and repairs of `.lean/lean/` still run, other writes are denied, and Stops fail closed with a block (`hooks/test_controls.py`).
  3. MEDIUM: `lean test --changed` counts every tracked path when there is no remote (`unit/test_testsel.py` NoRemoteTests: was `[]`).
  4. MEDIUM: impact rules win over lint-only globs (`.lean/templates/tracker.md` now selects the records tests; was lint only).
  5. MEDIUM: `spawn run` skips dependents of unsuccessful tasks and starts dependents from HEAD plus their dependencies' changes (`e2e/test_spawn_run.py`: was `done` and missing the file).
  6. MEDIUM: `lean update` replaces only Lean's hook entries and keeps the project's own hooks and status line, with a note (`e2e/test_update.py`).
  7. LOW: atomic writes keep the file's mode; new files get the umask mode (`unit/test_util.py`: was 0600).
  8. LOW: stale `.claude/.gate-cache` removed.
  9. LOW: receipt refusal names `lean evidence record-review` (`hooks/test_guard.py`).
  10. LOW: agents run in their own process group, which a timeout or exit kills; a run that errors stops and records running agents (`e2e/test_spawn_run.py`: grandchild survived before).
  11. LOW: the status line reports `LAST_PASS` without hashing the tree; `lean status`/`gate status` still verify.
  12. LOW: the update report lists every overwritten file (`replace`, `merge`, `write`) (`e2e/test_update.py`).
- Dispatch HIGH review round 2 | reviewer | size=L | requested model/effort=opus/high | context=fresh | verdict REWORK (second; one final pass remains, limited to these fixes): round-1 fixes 1–5, 7–9, 11, 12 confirmed; 7 findings (3 MEDIUM, 4 LOW).
- Round 2 fixes (final pass), each with a regression test that failed first:
  1. MEDIUM: a covering review accepts controls whose names changed (4.x baseline): `controls_at` reads every name either side has (`hooks/test_controls.py`).
  2. MEDIUM: `lean update` refuses registry, plan, link and journal paths outside the target (absolute, `..`, symlinked parents) (`e2e/test_update.py`: a tampered plan had written `../escaped.txt`).
  3. MEDIUM: `.lean/tests/impact.json` is a gate control (`hooks/test_controls.py`).
  4. LOW: an agent's process group is killed after a clean exit too (`e2e/test_spawn_run.py`: a background child survived).
  5. LOW: when the package cannot load, a continued Stop is released UNVERIFIED instead of looping (`hooks/test_controls.py`).
  6. LOW: `.codex/hooks.json` is merged like `.claude/settings.json`, keeping project hooks (`e2e/test_update.py`).
  7. LOW: docs and policy state that CLI-stored API-key logins are outside the environment stripping.

## Evidence guidance

Record commands, results, and review findings before marking DONE. For each delegated assignment, reassignment, or model/effort change, add the compact dispatch records defined in `.lean/skills/lean-agents/SKILL.md`.

- Contract replaced 2026-10-26 (scope change D22–D24); the previous contract's review cycle ended after its second REWORK, whose fixes are in this shipping state; the new contract's review covers everything.
- `hooks/test_target.py` 31/31; `e2e/test_spawn_scenarios.py` 7 scenarios; `unit/test_activity.py` 6.
- Dispatch HIGH review (contract 2) round 1 | reviewer | size=L | opus/high | fresh | REWORK, 7 findings (1 HIGH, 1 MEDIUM, 5 LOW). Fixed with fail-first regression tests:
  1. HIGH: target check output reached the Stop's stdout and broke its JSON (fail open); output is now captured (`hooks/test_target.py`).
  2. MEDIUM: the refusal reason carries the target command's last 40 lines (same test).
  3. LOW: `lean log` reads times without a zone as UTC instead of crashing (`unit/test_activity.py`).
  4. LOW: option abbreviations are refused (`allow_abbrev=False`) and `--opt=value` forms count for the guard (`unit/test_cli.py`, `hooks/test_guard.py`).
  5. LOW: a broken activity module never blocks a declaration (`hooks/test_controls.py`).
  6. LOW: `lean spawn run` refuses while a target is selected (documented; `hooks/test_target.py`).
  7. LOW: docs say `xN` runs up to N at once.
- After the fixes: `lean test --all` 25/25 on Python 3.14 and 3.9; every gate command exits 0.
- Dispatch HIGH review (contract 2) round 2 | reviewer | opus/high | fresh | REWORK (second; final pass limited to these): round-1 fixes 1–3, 5, 6 confirmed.
  1. `lean evidence` subcommands still accepted abbreviations (`--contr` filled `--contract`, letting the author's thread record its own receipt); the regression test passed for the wrong reason. Subparsers now use `allow_abbrev=False`; the rewritten test (`unit/test_cli.py`) failed first (`--contr` reached the receipt check) and passes now.
  2. `docs/skills.md` and `docs/migrating-to-v5.md` now say `xN` runs up to N at once.
- Dispatch HIGH review (contract 2) final pass | reviewer | opus/high | fresh | PASS (`reviewer-subagent-opus-c2r3`); both round-2 fixes confirmed, including a revert check showing the test fails without the fix. Index entries staged as deleted were re-staged with the reviewed bytes (`git add -A`); `lean evidence check-review` then exited 0.
- `lean gate run --cache-tree --session <this session>`: controls accepted by the covering HIGH review; 5/5 checks passed; Quality Gate: PASS.
- Deferred, non-blocking: one unidentified failure in one of four full Python 3.9 runs during the final review (25/25 in the other runs; suggested: keep failure names in the `lean test` summary); the guard misses a Lean call after Python options with values; an unparseable `lean log --since` is ignored silently; D12 above says "exactly N" where the shipped behavior is up to N at once.
  Not taken in the final pass (non-blocking notes, recorded for later): guard misses a Lean call after Python options with values (`python3 -X utf8 .lean/bin/lean ...`); an unparseable `lean log --since` is ignored silently.

## Next step

Done. Follow-ups are listed under Evidence (deferred notes); commit and release are separate requests.
