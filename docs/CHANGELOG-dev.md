# Lean 5.x — technical changelog

Developer and agent notes for each 5.x release: commands, flags, rules, changed gate controls and limits.
The user-facing summary of each release is in [`.lean/CHANGELOG.md`](../.lean/CHANGELOG.md).

## 5.4.1 — 2026-10-30

First published intake/batch release; 5.4.0 remains a tagged CI candidate, not a GitHub Release.

- The inherited controller-takeover regression used `/Users/x10/.claude/projects/p/memory/MEMORY.md`. This correctly fails the guard on Linux, where that path is not the user's memory directory. Build the same assertion from `Path.home().resolve()` as the adjacent memory regression already does. The guard implementation and its rejection rules are unchanged.
- Fail-before evidence: both Ubuntu Python 3.9 and 3.13 jobs in the 5.4.0 branch/tag CI runs failed at that assertion. Local macOS validation had passed, demonstrating the host-specific test assumption. CI runs: 41039552084 (tag), 41039551870 (branch).
- Includes all compatible 5.4.0 capabilities and upstream 5.3.1 fixes. Do not move or replace the pushed 5.4.0 tag; validate and publish a fresh 5.4.1 tag.
- Changed controls relative to 5.4.0: version metadata only. Full release tests, independent HIGH review and shared gate are required before publishing.

## 5.4.0 — 2026-10-30

Compatible, opt-in requirement intake and bounded shipping batches. Includes the upstream 5.3.1 guard and per-session progress fixes.

- **Intake.** `lean intake add|list|check|cancel` records classification, task, acceptance, dependency and supersession links. New entries queue by default. Deterministic checks refuse missing traceability, invalid links, cycles and conflicting primary ownership. The model proposes priorities; the user decides material trade-offs.
- **Batches.** `lean batch start|checkpoint|resume|freeze|reopen|scope|retire|review|readiness|finish` separates intake from execution. Freeze snapshots scope and contract; a redirect invalidates readiness and requires a new contract. Retirement releases requirements for explicit cancellation/supersession, never completion.
- **Readiness and evidence.** Implementation READY is a Controller declaration, not acceptance proof. Review and gate cover the whole shipping checkout. Below HIGH depth, semantic review may be attested against shipping bytes and the reviewed Git base; HIGH still requires the independent receipt. A stale or deferred gate cannot close a batch. Ledger declarations remain attestations; hook-wide enforcement and evidence portability are follow-ups.
- **Targets and inspection.** Ledger records follow the selected record root; receipts, gate and fingerprints use the workflow root and include application submodule content. The target intake ledger receives the tracker semantic-review exclusion while its final bytes remain gate inputs. Read-only commands create no runtime files.
- **Compatibility.** No mode/configuration/data migration; no full-mode lease requirement. Existing installations without a ledger are unchanged. See [workflow guide](workflow.md#optional-intake-and-bounded-batches-all-modes).
- **Validation.** Public-CLI regressions cover lifecycle, dependency cycles, WIP, frozen scope, staged/working-tree gaps, read-only inspection and selected-target review/gate/application drift. Release requires the full test suite, independent HIGH review and the shared gate after integration.
- Changed controls: `cli.py`, `intake.py`, `records.py`, `evidence.py`, `guard.py`, version metadata and the test impact map. Policy and skill guidance define bounded intake without introducing task-scoped gate-coverage claims.

## 5.3.1 — 2026-10-29

Findings from Casetodian's audit after applying 5.3.0 (TCK015).

- **Guard help flags.** `guard.lean_writes` counts `-h`/`--help` as usage text only before `--`; `lean gate scope` with a command is always a write (only bare `lean gate scope -h|--help` reads). In 5.3.0 any `-h` made the call a read, so `lean gate scope -- <command> -h` ran `<command>` without a contract or takeover check (the 5.3.0 note that the guard treats `gate scope` as a write did not hold). Test: `hooks/test_guard.py::AuditHolesTests::test_help_flag_after_double_dash_or_in_gate_scope_is_still_a_write`.
- **Memory exception.** `guard.external_scratch_or_memory` allows, besides `/tmp` and `/private/tmp`, only a flat `<base>/projects/<project>/memory/<file>` whose `<base>` is resolved `~/.claude`, `$CLAUDE_CONFIG_DIR` or `.../claude-profiles/<name>[/home]` under the user's home. 5.3.0 allowed any outside path containing `/memory/` and `/.claude/` (or `claude-profiles/`), such as another checkout's `.claude/hooks/memory/x.sh`. Test: `test_memory_exception_covers_only_user_memory_files`.
- **Gate caches and runtime write checks.** `guard.GATE_CACHES` (`.agent-runtime/gate-cache`, `.agent-runtime/target-gate-cache`) take the receipt write check (`writes_receipt`), with or without a contract; `rm` and reads stay allowed. `writes_receipt` now compares targets with `names_target()` (`os.path.normpath`, case-folded on macOS), counts every file redirection (`FILE_REDIRECTS`: `&>`, `&>>`, `>>|` too), and prefilters on the file name, so `./`, `//`, `..`, case variants and `&>` no longer bypass the receipt, pending-marker and cache checks. Test: `test_gate_caches_are_never_written_directly_even_with_a_contract`.
- **Interpreter options.** `guard.interpreter_script` skips python's valued options (`-X`, `-W`, `-Q`) and stops at `-c`/`-m`/`-`, so `python3 -X dev .lean/bin/lean gate scope -- rm x` is checked as a `lean` call (it was a read).
- **Per-session progress.** `progress.update/load/clear` take a session (default `env_session()`: `LEAN_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`; ids must match `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`, else shared). State goes to `.agent-runtime/progress/<session>.json` and `progress.json` (latest, with `session`); files older than 7 days are pruned on update; a session's first update keeps the task of an unowned or own shared state. `progress.shown()` labels another session's state `session <id8>:`. `lean status --line` reads `session_id` from the status-line stdin JSON; Claude SessionStart/Stop and Codex SessionStart/Stop pass the hook payload's session; `lean spawn run` reads each agent worktree's latest state. Tests: `unit/test_progress.py::SessionTests` (hook messages included).
- Changed gate controls: `.lean/lean/__init__.py`, `guard.py`, `progress.py`, `cli.py`, `hooks.py`, `spawn.py`. Validation: `lean lint`, `lean test --changed`, gate, independent HIGH review (round 1 REWORK on cache-path spellings, fixed).

## 5.3.0 — 2026-10-28

Findings from the first production run (Casetodian workspace with a submodule application target): TCK013 and TCK014.

- **`lean gate scope [--only GLOB]... [--always GLOB]... -- <command>`** (`testsel.scoped`, `scope_skip`). Runs one gate check unless every path of `testsel.scope_paths()` for the repository holding the working directory matches `testsel.RECORDS` (`docs/tracking/*`, `.agents/queue/*`, `.lean/targets/*/docs/tracking/*`, `.lean/targets/*/.agents/queue/*`) or `--only`, and none matches `--always`. A skip exits 0 and prints `gate scope: skipped <command>; N changed path(s) are work records only`. `scope_paths()` diffs the working tree and index against the merge-base with the first remote's `HEAD`, `main` or `master` (so pushed but unmerged commits count, unlike `changed()`), with `--ignore-submodules=none` (an untracked file in a submodule or a submodule commit counts despite `submodule.<name>.ignore` or `diff.ignoreSubmodules`), plus untracked files. Runs on `LEAN_GATE_SCOPE=full`, an empty change, no repository, no resolvable default branch or a Git error. The command runs without a shell in the caller's working directory; its status passes through, a missing command is 127. The guard treats `lean gate scope` as a write (it runs an arbitrary command). Tests: `unit/test_testsel.py::GateScopeTests`. Ported from Casetodian's `scripts/gate_scope.py` (TCK424), generalised from its fixed target paths.
- **Rules** (`QUALITY.md` "Change-scoped checks, batches and flaky failures", `RECOVERY.md`, `lean-gate`): scope only code suites; a batch of TCKs runs one full gate covering every task's final state (one per published part); a suspected flaky failure gets at most 2 unchanged reruns, passes only if a rerun passes, and is recorded otherwise.
- **Test selection** (TCK013). `impact.json` `lint_only` includes `.lean/targets/*`, `.agents/queue/*`, `docs/tracking/*`; these run lint only when no rule matches. Test: `unit/test_testsel.py::test_target_and_queue_work_records_are_lint_only`.
- **Target gate cache** (TCK013). With `--cache-tree`, `target.gate` reuses a pass recorded in `.agent-runtime/target-gate-cache` keyed by target name, SHA-256 of the target PROJECT file and `evidence.state(target_root)`; `guard_controls` and `high_risk_changes` still run. Check counts include target checks; `activity.jsonl` records the first non-progress failure line. Tests: `hooks/test_target_gate.py`.
- **Guard** (TCK013). Reads: `lean <group> -h/--help`, `git submodule status|summary`, input redirections (`< $var`). Writes allowed to `~/.claude/**/memory/`, `/tmp`, `/private/tmp`. Controller session supersede/takeover protection. Tests: `hooks/test_guard.py`.
- **`/lean-agents`** (TCK013): 3-5 task batches, shared-foundation-first waves, bounded polling, controller handoff hygiene (`docs/agents-and-models.md`).
- Changed gate controls: `.lean/lean/__init__.py`, `cli.py`, `testsel.py`, `gate.py`, `target.py`, `guard.py`. Validation: `lean lint`, `lean test --all`, gate, independent HIGH review.

## 5.2.3 — 2026-10-28

Documentation only; no workflow behaviour changes.

- **Workflow map.** `docs/workflow-map.md`: one Mermaid flowchart of every path through contract, scope, implement, test, validate, review and gate (trivial vs non-trivial, mode, execution, review depth and rounds, gate mode and outcomes), with notes linking WORKFLOW.md, REVIEW.md, QUALITY.md and RECOVERY.md. Linked from README.md and `docs/workflow.md`.
- **Spawn map.** `docs/spawn-map.md`: an overview flowchart of MODELS.md spawn levels, size choice, dispatch and escalation (fix at source, fresh remainder, one effort step, then one size; 2XL and 3XL only by escalation), and one size ladder each for Claude, Codex and agy from the shipped `.lean/models.json` (checked 2026-10-27). Linked from README.md and `docs/agents-and-models.md`.
- Escalation stays within one provider; agy past `XL` (2XL and 3XL share its model) reports BLOCKED. The maps describe the current policy and add no rule.
- The ladders name concrete models and must be updated with `.lean/models.json` (for example after `/lean-model-update`).
- Changed gate controls: `.lean/lean/__init__.py` (version only). Validation: `lean lint`, `lean test --all`, gate.

## 5.2.2 — 2026-10-27

- **Update clone.** `update.checkout` clones with `--no-local`, so a local release source is read through Git's pack transport instead of copied object file by object file. CI failed repeatedly in `e2e/test_update.py` with `fatal: failed to copy file to '<release>/.git/objects/..': No such file or directory` during that copy; reruns passed. Test: `e2e/test_update.py::test_release_sources_are_cloned_through_the_pack_transport`.
- **Guard.** `unknown_word()` (a `$`, backtick, `*`, `?` or `[` in the word) makes the deciding word of `git reflog` and the name of `git symbolic-ref` count as writing, as `git stash $X` already did. Test: `hooks/test_guard.py::test_an_expansion_or_glob_in_the_deciding_git_word_is_a_write`.
- **Codex markers.** `clear_codex_session_refusals` handles each marker in its own try. Test: `hooks/test_gate_mode.py::test_a_new_session_clears_each_codex_marker_independently`.
- Changed gate controls: `.lean/lean/update.py`, `guard.py`, `hooks.py`. Each new test fails on 5.2.1.
- Correction to 5.2.1 below: its tests also include `hooks/test_gate_mode.py::test_clearing_codex_markers_removes_each_one_independently`.

## 5.2.1 — 2026-10-27

Hardening ported from Casetodian's local patches to its Lean 4.x tooling (compared with Lean 4.16.0), the `lean models` guard gap from 5.2.0, and the readable changelog.

- **Guard, git.** `reflog` and `symbolic-ref` leave `READ_GIT`. `git reflog` writes when its first non-option word is `expire`, `delete`, `drop` or `write`; no word, `show`, `list`, `exists` or a ref name read. `git symbolic-ref` reads only with exactly one name and options from `-q`, `--quiet`, `--short`, `--recurse`, `--no-recurse` (an allowlist, because git accepts bundled `-qd` and abbreviated `--del`); anything else writes.
- **Guard, lean.** `LEAN_READS["models"]` is `{"list", "check", "bank"}`; a bare `lean models` reads (`LEAN_DEFAULT_READS`). `apply` and `eval` need a contract.
- **Codex refusal markers.** `codex-gate-failed` and `codex-gate-refusal` are read, written and removed through `.agent-runtime` opened with `O_DIRECTORY | O_NOFOLLOW`, each marker with `O_NOFOLLOW`, accepted only as a regular file with one link; removal unlinks the name itself. A symlinked marker or folder raises, so the Stop counts as an unusable marker: a fresh Stop blocks, a continued one is released UNVERIFIED.
- **Changelog.** `.lean/CHANGELOG.md` 5.x entries are user-facing (Thai, then English, nothing collapsed, a first-line link here); the former English technical text of 5.0.0-5.2.0 lives below unchanged. Rules: `docs/development.md` "Writing the changelog".
- Changed gate controls: `.lean/lean/guard.py`, `hooks.py`.
- Tests: `hooks/test_guard.py` (`test_git_reflog_and_symbolic_ref_write_unless_they_only_read`, `test_lean_models_apply_and_eval_are_writes`), `hooks/test_gate_mode.py` (`test_a_planted_codex_marker_link_is_never_followed`); each fails on 5.2.0.
- Not ported: Casetodian's other local patches (4.x updater `takeover.py`/`shared_assets.py`, `check_structure.py` tracker paths, `gate_mode.py` permission preservation) are replaced or already covered in v5.

## 5.2.0 — 2026-10-27


Refresh the model list from evidence. No token or speed saving is claimed for the workflow itself.

**Added**

- `/lean-model-update`: research the models each provider offers, agree an eval plan and a token cap with the user, run the eval, have an independent reviewer check the results, and write `.lean/models.json` only for the proposal the user approved. It never edits provider permission settings; for agy it gives the user the allow rules to add.
- `lean models eval --plan FILE --budget TOKENS [--estimate N] [--out DIR]`: runs each candidate (provider, model, effort) on the task bank in throwaway Git copies outside the repository, with the `models.json` command shapes, eval-only flags (Claude may run `python3 -m unittest`) and metered API keys removed, and scores hidden tests per subtest. Each run reserves the larger of the largest token count seen and `--estimate` (default 250000), starts only while spent plus reservations fit the budget and otherwise waits for running ones, so only a run that uses more than its reservation can go over; a CLI that never started costs nothing and is retried, an unknown count costs exactly its run's reservation, and a run that fails in any step is recorded and releases its reservation. Tokens follow one rule for every provider (input + cache writes + output, cache reads apart; Codex reports one total); an unknown count is charged like a reservation. Writes `results.jsonl` (a rerun resumes), `summary.md`, `proposal.json` (per provider and size, the fastest candidate with a full score) and raw `logs/`. Permission denials are reported as notes.
- `lean models apply --proposal FILE --sha256 DIGEST`: writes only the proposed sizes, refuses a proposal that changed since its digest was shown, and validates the list.
- `lean models bank` and the task bank in `.lean/evals/` (workflow-owned, shipped with every installation): one task per size, from a one-line bug fix (3S) to a single-flight thread-safe cache (3XL), each with a reference solution that scores full marks and a stub that does not.

**Upgrade:** `python3 .lean/bin/lean update preview`, review the plan, then `update apply`; `.lean/evals/` arrives with the release. The changed gate controls (`.lean/lean/evals.py`, `models.py`, `cli.py`, `structure.py`) need a covering HIGH review or `lean gate accept-controls`. No configuration or data migration.

## 5.1.0 — 2026-10-27


Eight spawn sizes instead of four. No token or speed saving is claimed for the workflow itself; the size mapping follows the [2026-10-27 model eval](benchmarks/2026-10-27-models/README.md).

**Added**

- Sizes `3S`, `2S`, `S`, `M`, `L`, `XL`, `2XL`, `3XL`, smallest first: two cheaper sizes for locating and small mechanical work, two stronger ones for work `XL` could not do. `lean models`, `lean models check [--live]` and `lean spawn plan` know all eight.
- The shipped `.lean/models.json` (checked 2026-10-27) maps them per provider. Claude: Haiku low/medium, Sonnet low/medium, Opus high/xhigh, Fable high/max. Codex: `gpt-6-luna` low, `gpt-6.1-terra` low/medium, `gpt-6.1-sol` medium/high, `gpt-6-astra` high/xhigh/max. agy: Gemini 3.8 Flash low/medium/high, Gemini 4 Argon low/medium/high (high for `XL` to `3XL`). Codex `ultra` effort is not used.

**Changed**

- Changed mappings in the shipped list (old → new): Claude `S` Haiku low → Sonnet low, `XL` Fable high → Opus xhigh (Fable is now `2XL`/`3XL`); Codex `S` `gpt-6-luna` low → `gpt-6.1-terra` medium (Luna is now `3S`); agy `S` Flash low → Flash high, `M` Flash high → Argon low. Every other `S`/`M`/`L`/`XL` mapping is unchanged. The old `S` is closest to the new `3S`; the old Claude `XL` is the new `2XL`.

**Upgrade:** `S`, `M`, `L` and `XL` stay required and the new sizes are optional, so a project's 5.0 `models.json` keeps working; a task sized with a size the project does not define is refused with a message (an explicit `--model` still runs). To use the new sizes, copy the `tiers` you want from the release's `.lean/models.json` and run `lean models check --live`. The changed gate controls (`.lean/lean/models.py`, `spawn.py`) need a covering HIGH review or `lean gate accept-controls`.

## 5.0.2 — 2026-10-27


Follow-ups from the 5.0.1 release work. No token or speed saving is claimed.

**Fixed**

- In Claude, `lean contract declare` exits 2 with "NOT bound" when no session holds the contract it was given, as when the contract comes through a shell variable or after another command and the guard's hook does not bind it. It used to print the contract as if bound while the session kept its earlier one. Other runtimes (Codex without trust, agy) still only validate, and `lean spawn run` no longer passes Claude's `CLAUDECODE` marker to its workers.
- `lean lint` reports a routed document that is not UTF-8 text instead of stopping with a Python error.
- `lean update preview` reads a symlinked routed document the way lint does when the link resolves inside the project, and never one that points outside it; it notes a routed document that is not UTF-8 text, which lint reports.
- A busy-gate Stop is counted per session, so another session's fresh Stop no longer restarts this session's count; counters older than a day are removed.
- REVIEW.md: request the HIGH review before committing changed gate controls; a receipt cannot accept a control change committed before the review began.

**Upgrade:** `python3 .lean/bin/lean update preview`, review the plan, then `update apply`. The changed gate controls (`.lean/lean/gate.py`, `guard.py`, `cli.py`, `spawn.py`, `structure.py`, `update.py`) need a covering HIGH review or `lean gate accept-controls`. No configuration or data migration.

## 5.0.1 — 2026-10-27


Fixes found upgrading a real 4.16 project to 5.0.0, and the Low findings from the 5.0.0 reviews. No token or speed saving is claimed.

**Fixed**

- Lean's own tests pass in an installation whose PROJECT.md names its own `.lean/` files (such as `.lean/LOCAL-EXTENSIONS.md`): the release copy the tests build now brings the project files those documents name. A routing test no longer assumes PROJECT.md ends inside its Documentation routes section. Before, `unit/test_structure.py` failed 4 tests there.
- `lean update preview` names what `lean lint` would reject after the update: a project's own file inside a workflow-owned folder (kept, never deleted) and 4.x paths in the documents PROJECT.md routes to (such as README.md).
- A Codex Stop with a symlinked `.agent-runtime` blocks a fresh Stop and releases continued Stops UNVERIFIED instead of blocking them without end.
- `lean test` takes a tier name (`lean test e2e`) and repository paths (`.lean/tests/hooks/test_gate.py`) as well as `hooks/test_gate.py`, and names an unknown file instead of a Python error.
- A review-pending marker releases control drift only when the contract it was matched with is the session's HIGH-depth contract; a Stop run by hand with another `--contract` still blocks.

**Upgrade:** `python3 .lean/bin/lean update preview`, review the plan, then `update apply`. The changed gate controls (`.lean/lean/gate.py`, `hooks.py`) need a covering HIGH review or `lean gate accept-controls`. No configuration or data migration.

## 5.0.0 — 2026-10-27

**Token highlight:** fixed-task inventory 11,146 → 9,962 (-10.6%), startup 2,213 → 2,209 (-0.2%), o200k_base ([measurement](benchmarks/2026-10-27/README.md)) · **Compared with:** 4.17.1

Rebuild the workflow around one `lean` command line. Every rule, hook and check from 4.17.0 that the core keeps carries over with its tests; the layout, commands and spawning defaults change, so this is a major release.

- **One command.** `python3 .lean/bin/lean` replaces every script in `.lean/scripts/`, the Claude hook scripts and the Codex adapter. Code lives in `.lean/lean/`, one module per command group (`guard`, `gate`, `evidence`, `hooks`, `records`, `progress`, `models`, `spawn`, `testsel`, `structure`, `update`). Provider hooks call `lean hook claude|codex <event>`. The bash gate runner is now Python; ShellCheck is no longer needed.
- **Progress bars.** `lean progress set <phase>` drives a solid/shade bar (`████████░░░░░░░░░░░░ 40%`) by lean-task phase, refined by counts inside a phase. One state file feeds the agent's replies, `lean status`, `lean watch`, `lean test`, `lean gate run`, `lean spawn run` (one bar per agent), the Claude status line and Codex's Stop message. Codex and agy have no custom in-window status line; they use `lean watch` in a second pane.
- **Tests by impact.** Tests sit in `.lean/tests/unit`, `hooks` and `e2e`; `.lean/tests/impact.json` maps paths to them. `lean test --changed` runs only what the change can affect, documentation-only changes run lint only, and an unmapped path runs everything. The gate runs the selection; CI runs `lean test --all` on every push and pull request.
- **Model list and spawning.** `.lean/models.json` maps sizes S/M/L/XL to models for Claude, Codex and agy; `lean models check --live` verifies them against the provider CLIs. By default at most `max_agents` (1) sized agent runs at a time, only when cheaper than finishing in the session. `/lean-agents` spawns one agent per parallel task; `/lean-agents <model> xN` runs up to N at once on that model. `lean spawn plan` computes waves with exclusive file ownership; `lean spawn run` starts headless `claude -p`, `codex exec` or `agy -p` processes in separate worktrees, removing metered API keys so they use the subscription login.
- **Activity log.** Phase changes, gate runs, test runs, spawned agents, contract bindings and review receipts are timed in `.agent-runtime/activity.jsonl`; `lean log` shows the timeline or a per-phase summary and `--export` keeps a copy in the repository.
- **agy support.** Antigravity CLI is a third provider for spawning, review and the gate (run explicitly; agy has no hooks).
- **Smaller core.** Eleven skills remain: init, task, scope, research, grill, agents, review, gate, effort, update and target. The optional skills audit, catalog, compress, pattern, playbook, prune and takeover are removed with their tools, along with the optional skill pack and queue cleanup (`clean-queue`). Archived queue history stays readable. Application targets (`lean target use|context|clear|gate`, records in `.lean/targets/<name>/`) carry over unchanged in behavior. The shared "skill level" text moved into `policy/SKILL-EFFORT.md`.
- **Update with migration.** `lean update preview|apply|rollback` replaces the takeover-based updater: an external pinned clone, a reviewed plan, snapshots, a journal and rollback, with 4.x migration of hooks, gate block, gate mode and skill links.
- **Quiet Stops while a review runs.** `lean gate review-pending --contract ... --session ...` marks an independent review as running; that session's Stops whose only refusal is the missing receipt for the same contract and shipping state are released UNVERIFIED (never passed) for up to two hours, instead of being refused again. Under a HIGH-depth contract, changed gate controls waiting for that review are released the same way, with checks NOT_RUN. Any change, another contract, a recorded receipt or any other refusal ends it. Only the command writes the marker.
- **Trusted spawn runs.** `lean spawn run --trust-agents` adds each provider's `trusted_args` from `models.json` (agy `--dangerously-skip-permissions`, Claude `--permission-mode bypassPermissions`), so headless agents can run their task's commands; it warns and is never the default.
- **Faster hooks and commands.** Measured against 4.17.1 on one machine with a trivial gate: a Stop takes 125 ms instead of 730 ms and starts 6 `git` processes instead of 11, SessionStart 128 ms instead of 627 ms, and plain commands are within 6 ms of 4.17.1's scripts (53–55 ms). The CLI keeps compiled bytecode in a private per-user cache (`~/.cache/lean-workflow/pycache`, or under `$XDG_CACHE_HOME`; used only when the path is absolute and every directory from the cache base down is the user's own and not writable by others, never in the checkout; delete it to clear it), the status line reads the gate's markers without loading the gate, and AGENTS.md is shorter with every rule kept. Data: [docs/benchmarks/2026-10-27](benchmarks/2026-10-27/README.md).
- `lean test` names failing test files in its summary line.
- A Claude Stop that finds the gate lock held by another run is blocked at most three times, then released UNVERIFIED, as in 4.17.1; it records no pass. The lock is an `flock` the kernel drops with its holder, so v5 needs no guardian process or `ps`. Checks inherit it, so unlike 4.17.1 a process a check leaves running in the background keeps the checkout locked until that process exits. A busy counter or refusal marker that cannot be written no longer blocks continued Stops without end.
- Gate mode moves from `.codex/quality-gate.json` to `.lean/gate.json` (`lean gate mode`). Gate runtime markers move from `.claude/.gate-cache`/`.gate-failed` to `.agent-runtime/`.

**Upgrade:** this release changes paths and commands; follow [migrating to v5](migrating-to-v5.md). A 4.x installation has no `lean` command, so run the preview from the pinned 5.0.0 release: `python3 <release>/.lean/bin/lean update preview --target <project>`, review the plan, then `update apply`. Approve the changed gate controls through a covering HIGH review or `lean gate accept-controls`. Project records, PROJECT facts, config and trackers are kept.
