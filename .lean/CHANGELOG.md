# Changelog

Versions follow `MAJOR.MINOR.PATCH`. MAJOR changes workflow rules, or moves files an existing
install depends on. MINOR adds rules or files, and covers making an existing rule hold where it
was being bypassed -- the rule did not change, its enforcement did. PATCH clarifies wording.

## Unreleased

- Trim the text loaded into every turn, keeping every rule. `AGENTS.md` and the router it imports no longer state the same thing twice, the router drops setup and downgrade detail that `policy/WORKFLOW.md`, `OPTIONAL.md` and `CUSTOMIZING.md` already hold, every skill and reviewer description is shorter (the trigger stays), the `auto=false` session message is shorter, and `AGENTS.md` gains one rule: batch independent tool calls in one turn and do not repeat a call whose result you already hold. Measured with a one-turn Sonnet probe on a project that adds its own sizing table and agents: the first turn read 28,513 tokens against 29,859 before. Separately, a project can hide tools and skills it never uses from every request through its own `.claude/settings.json` (not part of the template): `permissions.deny` for `Workflow`, `ScheduleWakeup`, `ReportFindings` and `ListAgents`, and `skillOverrides` set to `user-invocable-only` for built-in and optional skills. That took the same probe to 20,720 tokens, 27% below the 4.1.0 setup (28,319), and `/name` still works for a hidden skill. Over 16 smoke runs the result used 103k tokens per run against 136k for 4.1.0 and 145k for 4.3.0, with the same task results, the contract line first in 16/16 runs, and the independent reviewer dispatched in 4/4 auto-gate runs.
- Cut the turns the contract guard and Stop gate add, keeping every rule. In a Sonnet smoke test against 4.1.0 (same four tasks), 4.4.0 used about 15% more tokens, mostly from extra turns: a `contract_guard.py declare` call, a `git diff` rerun to "verify" an edit, a denied first shell read, and Stop refusals that named control drift and the High-risk review one Stop apart. Claude's PreToolUse guard now binds the contract from the first text of the reply to the latest person prompt, read from the transcript (runtime turns, compaction summaries and tool results continue the turn; a later, earlier-turn or subagent contract does not count). It binds before the own-receipt check, and re-reads for up to 1s because Claude can persist that text just after the hook starts. Codex, or a session without a readable transcript, still declares, and the denial says so. Plain shell reads (`grep`, `cat`, `head`, `tail`, `wc`, `ls` and read-only `git` subcommands, alone or piped, with no operator characters, expansion or newline) run before a contract. `AGENTS.md` says a successful edit, test or gate result already verifies a change. A control-drift refusal also names the High-risk changes that will need HIGH review, and `check-review` says which part of a receipt differs (verdict, exact contract, shipping state). `AGENTS.md` and the router drop wording that `REVIEW.md`, `QUALITY.md`, `MODELS.md`, `OPTIONAL.md` and the multi-agent skill already state. Measured on a 4.3.0 project, the result used 0.8% more tokens than 4.3.0 over 16 runs (4.8% fewer in the last 8), with the contract line first in 16/16 runs instead of 11/16 and the same task results. The guard still fails closed.
- Accept protected gate controls that equal a trusted upstream ref without a manual step. PROJECT.md may list remote-tracking `refs/remotes/*` names in one `<!-- trusted-control-refs: ... -->` line; when every control matches one of them, `gate_evidence.py guard-controls` records an automatic acceptance naming the ref and commit, for Claude and Codex alike. Merging a reviewed release previously stopped every Stop until a person ran `accept-controls`, which an agent cannot approve for itself. Local edits, local branches, tags, `HEAD` and commit ids still need the manual procedure, Git replace objects are ignored, and the line is itself a control. Projects without the line keep their recorded baseline.
- Add `workflow.py context`, a read-only JSON summary (mode, active tracker and next step, claims, Git state, last gate result) for resuming work, and `workflow.py tracker archive --dry-run|--apply [--id TCKnnn]`, which moves `DONE` trackers (with all linked queue items DONE in full mode) to `docs/history/agent-workflow/`. Archived trackers stay resolvable by ID.

## 4.4.0 — 2026-10-17

- A turn whose shipping state equals the latest PASS receipt's state now meets the High-risk floor without a new review, under a later contract, when that receipt was recorded for a HIGH-risk or VERY_HIGH-quality contract (`gate_evidence.py check-shipped`); a PASS under a lower contract never required an independent reviewer and does not count. After a session committed High-risk paths, every later Stop (even a status reply) demanded a receipt for its own contract and was released UNVERIFIED. A HIGH contract still needs a receipt for itself, and any further change needs review.
- The receipt guard now also recognizes renamed, extension-less or copied `gate_evidence.py` scripts (by content, including a copy made in the same command) and `echo record-review | xargs ...` pipelines, and refuses Write/Edit/apply_patch targets, redirect targets and writer arguments (`cp`, `tee`, `sed -i`, ...) of `.agent-runtime/review.json`; reads and text that only mention the path are allowed. A write through a path the guard cannot see (`cd .agent-runtime && ...`) is a known gap.
- A crashing contract guard no longer locks the session out: a bug in it (not an undecidable input, which still denies) allows read-only tools and edits or `git checkout`/`git restore` of `.lean/scripts/contract_guard.py`, and denies everything else with a repair hint. A half-applied edit to the guard had blocked every tool, including the fix.
- `AGENTS.md`: report only changes verified after the last edit; a denied or failed tool call changed nothing. Evals add a `claims_match_changes` grader to every case: a reply that says a file changed when it did not fails (it catches the one known false claim among 116 saved runs and no others).

- Add `.lean/tests/run_tests.py`, which runs each test file in its own process, several at once. It covers the same files as `unittest discover`, fails when any file fails, and cuts the suite from about 140s to about 40s on an 8-core machine. CI uses it. The serial command still works.
- Add opt-in agent behavior evals under `evals/` (repository development only; not a portable asset). `evals/run_evals.py` copies the template into a temporary project with a tiny application and drives real `claude -p` sessions there, so CLAUDE.md/AGENTS.md, hooks, skills and the reviewer agent load as they do for users. Six cases grade, without a model judge, the contract line, trivial contracts, regression-test order, BLOCKED instead of DONE on a missing gate tool, reviewer dispatch for High-risk paths and stopping on an unresolved decision. Paid runs need `--model` and `--max-total-usd`; CI runs only the grader tests and `--dry-run`. No gate, hook or rule changes.
- Only the independent reviewer records a review receipt. In a `claude -p` eval, the background reviewer was refused a piped command (`... | tail`), and the author then recorded the receipt itself, so the receipt no longer showed an independent review. `policy/REVIEW.md`, `QUALITY.md` and `lean-review` now say the author never records it and reports BLOCKED instead. The contract guard denies a main-thread `record-review` naming the session's own declared contract, on both providers. It parses the command into shell words with operators split out, and checks any other argument that itself holds a command (`sh -c`, `bash -lc`, here-strings, `echo ... | sh`, `eval`); the `--contract` value and the contract text are data. A `record-review` call passes only with a literal `--contract` value that differs from the declared contract, so quoting, glued operators (`'...';echo`), wrappers and expansion do not hide it, while commands that carry the declared contract only as data (as a `--contract` value in either form, or quoted inside another argument such as a commit message) are not affected. Any other argument that holds a command mentioning `record-review` is parsed as a command, because a wrapper such as `eval` may run it. A standalone `record-review` word counts as a call only after `gate_evidence` (or a path hidden behind `$` or a backtick) in the same simple command, so `grep -rn record-review .` is not refused; subagents (`agent_id`) and separate reviewer sessions may record. Evals allow `tail`, `head`, `grep` and `wc` for reviewers.
- Claude's Stop adapter now refuses with `{"decision": "block", "reason": ...}` on exit 0 instead of exit 2. Headless `claude -p` reported an exit-2 Stop as "Stop hook error occurred" and ended the session with `success`, so a refused HIGH-risk change could finish without review; the JSON form feeds the reason back to the model, as Codex's adapter already did. SessionStart seeding and the UNVERIFIED release keep their behavior; if the JSON cannot be written, the adapter falls back to exit 2.
- Keep the contract as the first line of the reply. Evals after the contract guard showed Codex opening with a plan and declaring later, and Claude declaring without writing the line. `AGENTS.md` and `policy/CONTRACTS.md` now say the line comes before any preamble, plan or tool call, and that the declaration does not replace it. The reviewer role asks for each `gate_evidence.py` command on its own with a literal state value, because Claude refused to permission-check a `$(...)` record-review command.
- Evals: Codex runs use a temporary `CODEX_HOME` holding a 0600 copy of your `auth.json` and a config that trusts only the fixture, removed after each run. `--ignore-user-config` also dropped project trust, so no project hook (contract guard or Stop gate) had run in earlier Codex evals. Harness-fault detection now ignores agent text and tool output, which can quote the fault words.
- Enforce the Task Contract before writes, for Claude and Codex alike. New `.lean/scripts/contract_guard.py` runs as both providers' PreToolUse and UserPromptSubmit hook: shell, edit, MCP and unknown tools are denied until the session declares its contract with `contract_guard.py declare` (a single-quoted `--contract` or a quoted heredoc, no expansion or chaining), read-only tools stay available, subagents share the declaration, and a person's prompt clears it (runtime turns such as task notifications, agent hand-backs and hook feedback, including ones wrapped in a system reminder, do not). A contract may now be written as a `Contract:` block of `field: value` lines (`topic`, `risk`, `quality`, `budget`, `skill`, `acceptance`); its canonical one-line form is unchanged for receipts and `--contract`. Claude's Stop prefers the declared contract over the transcript, which a runtime may not persist in full; Codex's Stop now refuses changed work without a declaration, measured from a per-session baseline that a later SessionStart for the same session (resume or subagent) does not overwrite. Model is recorded from hook input when the runtime sends it (Codex does; Claude does not), and effort is not available to hooks. Upgrades must take `.claude/settings.json`, `.codex/hooks.json`, the Codex adapter, `gate_evidence.py`, `quality-gate.sh` and the new script together, re-trust Codex hooks, and record the control change with `accept-controls`.
- Fix `bash .lean/scripts/quality-gate.sh` with no arguments on macOS `/bin/bash` 3.2: re-running under the gate lock expanded an empty argument array under `set -u` and stopped with `gate_args[@]: unbound variable` before any check ran. Codex runs the gate this way; the Claude hook always passes arguments. A regression test runs the direct runner without arguments. Projects that patched the runner locally should take the upstream line.
- Require a Codex HIGH reviewer to start fresh. `AGENTS.md`, `policy/REVIEW.md` and `lean-review` now say to spawn it with `fork_turns: "none"` and give it the reviewer role, exact contract and diff range, never as a fork of the author's thread. A Codex eval run spawned the reviewer with `fork_turns=all`, so it saw the author's reasoning, which the existing independence rule already forbids. Projects carrying local edits to these files should merge the added sentence.
- Run the agent behavior evals under Codex too: `--provider codex` drives `codex exec --json` in the same fixtures, maps its events onto the graders' shapes and budgets with `--max-total-tokens`. Known gaps (heuristic shell-write detection, no per-run token cap, reviewer found from the stored session rollout and required to start fresh rather than fork the author's thread, no Codex Stop contract check yet) are listed in `evals/README.md`. Shell writes now count as file writes for Claude graders too. No gate, hook or rule changes.
- Speed up `test_template.py`'s installed smoke: the three configured-mode copies now run their nested suites concurrently instead of one after another. Assertions are unchanged; the file drops from about 35s to about 16s.

## 4.3.1 — 2026-10-16

- Let the installed template smoke tests pass in projects that own provider skills. While building its fresh copy, `test_template.py` dropped every undeclared `.agents/skills/*` and `.claude/skills/*` link, including project-owned links that project documents name, so the copy's structure check failed. Its discovery assertions also counted every entry, so project skill directories broke the expected 19 and 9. The copy now drops only undeclared links named after a canonical `.lean/skills/<name>` (local optional opt-ins), and the counts include only entries with a canonical `.lean/skills/<name>`. A downstream-shaped regression test covers both. This test-only patch changes no rule, configuration or record; projects carrying a local patch for it can take the upstream file on upgrade.

## 4.3.0 — 2026-10-15

- Make model sizing hold at dispatch. `MODELS.md` already chose the least costly capable model per task, but no spawn site passed one: the dispatch example recorded `inherited/inherited`, Codex fell back to "available defaults" and the reviewer's `model: inherit` read as the default. Every subagent therefore ran on the session model, usually heavier than the task. Each spawn whose tool accepts them now passes the sized model and effort, reviewers included; inheriting needs a recorded reason. Projects may map the rows to concrete models in Project additions or the catalog. The active session's settings, premium evidence, review depth and the reviewer definition are unchanged. The structure check rejects a policy without the per-spawn rule and an inherited dispatch example.
- Keep optional work in the active session when a spawn is not cheaper. A spawn costs a brief, cold re-reads and a handoff on top of the subagent's own work, so a session that already holds the context often finishes more cheaply itself. `MODELS.md` now spawns only when required (delegated execution, HIGH independent review, an explicit user request for workers) or cheaper, and favors spawns for large, read-heavy work a cheaper model can do without that context. Required delegation and review are unchanged; the structure check rejects removing the rule.

## 4.2.0 — 2026-10-14

- Allow an economical reviewer model for wording-only diffs in HIGH review. The reviewer checks a before/after rule map and hands meaning changes back to a normally chosen reviewer; the HIGH floor, independence, receipt and round limits are unchanged.

- Limit `/lean-compress` exhaustive reads to `workflow` audits. Named paths read their targets, AGENTS, the router and their dependencies, and escalate to a workflow audit when a target summarizes the whole workflow or its dependencies cannot be bounded.

- Complete approved audit remediation: template discovery contains only nine core skills, recommended standards remain nonblocking, and bounded audit behavior trials cover exceptions, missing evidence and unresolved decisions. Add shared auto/manual gate policy, an optional `lean-quality-gate-mode` command and Codex lifecycle adapter; missing preference preserves auto. Protect new controls and preserve project preferences during migration. Ten optional skills are available; manual skips remain NOT_RUN and never waive gate/review evidence. Codex hook trust remains runtime-owned.

- Add optional `lean-pattern` and `lean-audit` procedures with reusable project-standard and audit-finding formats. Reuse research/scope/Grill/task and project record routing; distinguish accepted requirements, exceptions, proposals and verification gaps. Nine core skills remain the default; the optional pack now exposes nine extras. Preserve previous 15/16-skill registries for migration. No new gate, automatic audit or automatic remediation/backlog is introduced.

- Clarify impact-based document and skill selection, cross-area dependency expansion and delta context on feedback. Keep required scope, high-risk Grill, review and gate checks; intensity does not activate extra skills. Add read-trace evaluation scenarios and shorten this repository's PROJECT map without changing its gate.

- Port reusable Casetodian extensions: shared standard/high/ultra procedure settings and a core `lean-skill-effort` command, with global/named choices, read-only inspection, reset and submodule record routing. Missing settings remain standard; project preferences never ship as release assets.
- Expose all discovered Lean skills to users while retaining the optional maintenance pack. Nine core and seven optional skills are available; previous eight-core/full registries remain readable during migration.
- Serialize shared gate runs with a per-checkout lock, report busy/unavailable as NOT_RUN and guard the lock helper as a gate control. Keep existing automatic/explicit gate behavior and opt-in whole-tree caching.
- Refuse new tracker IDs reserved by archived agent-workflow records, including nested history and Markdown/text records.

### Upgrade notes for these extensions

Merge canonical skills, policy, CLI, registry, discovery links, gate runner/lock helper and tests together. Preserve project `.lean/skill-effort.json` and per-target preferences; do not import downstream defaults, records or runtime hooks. Keep existing mode, execution and optional-pack choices. Merge the shared gate-mode helper, both provider adapters, optional command and tests together. Preserve workspace `.codex/quality-gate.json`; missing settings remain auto. No records-only cache or publishing is introduced.

- Opt this repository's Claude Stop command into tree caching; keep contract/review checks and fresh validation after changes or refusals. Document forced checks for environment/dependency changes and downstream opt-out; test the configured Stop command end to end.

- Add optional standard/high/ultra levels to scope, research and grill: preserve the default, deepen scope precision and question rounds, and broaden evidence-backed vendor/approach comparisons without changing workflow modes or authority.

- Keep nine core procedures in default discovery; expose seven bundled maintenance procedures through explicit `skill_pack.py enable|disable|status`. Retain canonical tools/tests/resources and accept legacy full discovery registries. Preserve existing project pack choices and custom slots during upgrades.
- Gate failures, including continued Stops, never become success after a retry cap. Missing/empty/malformed gates report undefined validation instead of passing silently. SessionStart records a change baseline rather than blessing a passing cache.
- Rerun checks by default; tree caching is explicit for Git-visible inputs only. Bind state to SHA-256 file contents, modes, symlinks, HEAD, index, controls and submodule work. Contracts come from parsed assistant text in the current human turn, before known write tools; unreadable supplied transcripts block.
- Release a Stop after three continued gate refusals with a user-visible UNVERIFIED message, so BLOCKED can be reported; a release keeps the refusal and never records a pass or cache. Do not treat runtime-injected skill, hook-feedback, task-notification or compaction entries as human turns. Require a HIGH review receipt when changes touch backticked paths/globs under PROJECT.md High-risk areas, including commits made since SessionStart.
- Bind HIGH-review receipts to exact contracts and shipping state. Track local gate-control drift and require recorded matching user approval for intentional changes. Document first-use trust, writable evidence, missing transcript metadata, Codex's explicit checks and external CI/merge authority limits.
- Shorten review/model/router prose. Keep the broad regression suite required before shipping behavior changes and in CI, with hook/discovery integrity checks in the turn gate.
- Add `lean-update-workflow` with pinned stable-tag acquisition, release/version checks, local customization reconciliation and existing takeover staging/approval/recovery. Preserve project-owned provenance and all project records; no automatic update or publishing. Treat source text as untrusted evidence; pinning does not authenticate publishers.

### Upgrade notes

Merge the runner, evidence helper, hooks, skills, registry and tests together; preserve PROJECT/config/records/permissions. Configure real project checks if the old gate was empty. Existing cache files are advisory only; seeding no longer makes validation pass. Optional discovery is a separate choice from mode/execution. Review and accept any intentional control changes using `gate_evidence.py accept-controls --reason '<matching user approval>'`; never use acceptance to bypass a failing check.

## 4.1.1 — 2026-10-14

### Clearer public documentation

- Rewrite the root README, CONTRIBUTING and all public guides in plain English with a more conversational tone. Keep the existing workflow concepts, commands and completion requirements.
- Make setup, modes, procedure intensity, delegation and runtime limits easier to follow. Correct the contribution guide to match nine core and ten optional skills, and include Codex lifecycle files in the repository map.
- Replace dated model-name examples and repeated delegation diagrams with capability-based guidance and links to official runtime documentation.
- Synchronize current baseline references. This patch changes documentation only; the extensions listed under Unreleased remain unreleased. No release tag or GitHub publication is implied.

### Upgrade from 4.1.0

Update the public guides and baseline references together. No configuration, record or runtime migration is required for this documentation patch. Preserve project-owned facts, commands, additions and preferences when merging.

## 4.1.0

### Evidence-backed repository cleanup

- Add `/lean-clean-repo` for whole-repository or path-limited audits of generated clutter, obsolete source/tests/dependencies/docs/assets/configuration and workflow files. Preview exact operations, reference edits, evidence, impact and validation before matching approval; retain uncertain/protected candidates.
- Add a Python helper with read-only inventory, exact-plan-ID apply, private external snapshots, per-operation journaling and guarded restore/resume. Preserve dirty/staged/untracked work by default, Git index, credentials, records/history and active instructions; reject symlink/hardlink/nested-repository boundaries, source drift and new descendants. Explicit regenerated selections require evidence in the approved plan. Stop repository writers during apply/restore. APPLIED still requires target checks and required review.
- Register the fourteenth canonical skill and both runtime discovery links; add isolated cleanup/recovery tests. No cleanup is run automatically during installation/upgrade.

### Upgrade from 4.0.x

Update the registry, shared-assets identities, canonical skill/tooling reference, helper/tests and both discovery links together. Preserve project facts/configuration, local skills and work records. Plans/snapshots belong in external private sessions and are not distributed. Existing queue cleanup and workflow ownership stay compatible.

## 4.0.0

### One shared source for Claude and Codex

- Move all thirteen skills and resources into `.lean/skills/`; replace runtime skill copies/adapters with individual relative discovery symlinks. Rename `/clean-queue` to `/lean-clean-queue` so all skill names use the `lean-` prefix; keep the underlying `workflow.py clean-queue` subcommand, input meaning and Claude command visibility. Provider-specific local extensions remain separate.
- Move reviewer instructions into `.lean/roles/reviewer.md`; Claude's reviewer entrypoint and Codex review routing use that source. Extract the Quality Gate into `.lean/scripts/quality-gate.sh`: direct calls always run; the Claude Stop adapter retains loop, seed, refusal and cache behavior.
- Add schema-2 release registry links, strict link/target integrity checks and recoverable takeover support for declared skill slots only. Preserve exact legacy directory snapshots and guard staging, interrupted apply/resume, rollback and post-approval drift. Schema-1 sources without legacy provider skill assets remain readable; upgrade a legacy skill baseline to schema 2 before drafting.

### Upgrade from 3.x

Update canonical skills/resources, both sets of discovery links, roles, runtime entrypoints, runner/tooling, tests, registry and documentation together. Preserve project additions, facts/config/catalog, records, target registrations and permissions. Before replacing a legacy Lean skill directory, fully read and reconcile local customizations into the canonical skill; preserve unrelated runtime skills. Use the reviewed takeover plan for lossless snapshots and guarded recovery. Copy links without dereferencing; a copied duplicate or incorrect target fails the structure check. Existing Claude cache paths and settings stay compatible. Restart/reload skills in existing sessions when necessary.

## 3.5.0

### Application submodules

- Add `/lean-use-submodule <remote url>` and a Codex adapter: Lean is the superproject, application code lives in `targets/<name>`, and workflow/project records stay outside the application repository.
- Add read-only preview, guarded add/reuse, pinned-commit branch recovery for clean detached checkouts, per-target context/records, explicit deselection and application gates. Preserve staged work and custom target instructions; stage only the submodule registration through Git, never commit or push automatically.
- Route workflow/catalog defaults to active target records, retaining explicit `--root` behavior and Lean template sourcing. Claude checks the application before its Lean cache can skip; Codex runs both gates explicitly. Add actual Git installation/reuse/clone, record isolation and gate tests. Upgrade all thirteen procedures/adapters, tooling, hooks and the assets registry together; preserve target registrations and records.

### Upgrade from 3.4.x

Update the contract/router, all shared procedures and matching adapters, tooling/hooks, tests and assets registry together. In Lean's own PROJECT gate, give workflow/catalog checks an explicit `--root .`; default commands now select active target records. Preserve target registrations, project data, runtime permissions and existing configured choices. The command keeps workflow outside the application Git history; it does not remove files already tracked there.

## 3.4.0

### Workflow takeover

- Add `/lean-takeover-workflow "<target path>"` with a shared procedure and Codex adapter. Audit the complete authorized workflow, ask adaptive Grill questions for material user decisions, and map old requirements/documents into Lean ownership before presenting an exact migration plan.
- Add external-session tooling for inventory/full-read attestations, release-registry baseline drafts, checked external staging, exact-plan approval, journaled apply/resume and guarded rollback. Preserve dirty/untracked originals and permission bits; reject private paths, nested repositories, source project capabilities, live Lean claims and stale revisions. APPLIED still needs target validation and HIGH independent review.
- Expand adapter parity and command visibility checks to twelve shared skills and six user commands. Add takeover behavior/recovery tests and usage/ownership guidance. The global Grill procedure is unchanged; additional decision depth applies to takeover.

- Support explicit lossless `casetodian-v1` queue/tracker conversion with accepted mapping decisions, inert originals, trusted staged record validation, and journaled recovery. Preserve existing Lean record guards and reserve cancelled queue IDs without inventing DONE evidence.

### Upgrade from 3.3.x

Update portable assets, the new `.lean/assets.json` release registry, tooling/tests and all matching adapters together. Preserve project additions, facts/gate, configuration, records, custom skills/agents and runtime permissions. No migration sessions or task records are shipped. Takeover is an explicit target operation; upgrading Lean does not run it or alter global skill discovery.

## 3.3.0

### Guard enforcement

Existing rules now hold where tracker layout, CLI input or filesystem paths could bypass them.
The rules are unchanged; their enforcement is stricter.

- DONE counts every unchecked checkbox under Acceptance criteria/Tasks headings at any level,
  including subheadings, suffixed headings, other bullet styles and items without an
  `AC-`/`TASK-` id. Checkboxes in other sections and inside code fences still do not count.
  Before upgrading, check or remove open boxes in DONE trackers: `check` now reports them.
- `tracker new --title` and `tracker status --evidence` must be single lines, so CLI text
  cannot add a second `Status:` line or a forged Evidence section.
- Agent ids with surrounding whitespace are rejected at claim time, and claim validation
  compares trimmed ids, so one agent cannot hold two claims as `A` and `A `.
- Workflow paths (config, `.gitignore`, runtime leases, tracking and queue) must not be
  symlinks; the CLI refuses to lock or mutate through them.
- The Quality Gate frames each untracked file by name and checksum, so redistributing bytes
  between untracked files invalidates a passing cache.
- Add regression tests for each guard and one end-to-end mode lifecycle test.

## 3.2.0

### User command entrypoints

- Expose five Claude commands for users: init, task, model update, compression and queue cleanup. Keep six agent procedures available internally with `user-invocable: false`.
- Document Codex skill invocation and its menu-visibility limitation; no custom-prompt installation. Add public argument hints and explicit preview-only queue arguments.

### Clarity-preserving workflow compression

- Add `/lean-compress` with a shared Claude/Codex procedure, complete-workflow read coverage, default preview and approved-scope prose edits. Preserve operational meaning, protected content, project additions and existing work; do not compress executable code or history.
- Document usage and add adapter presence/target tests. Creating the skill does not compress the workflow.

### Project model research tooling

- Add `/lean-model-update codex|claude|all`, a shared scope/research/grill procedure and Codex adapter, plus offline catalog check/preview/apply tooling.
- Preview is the default. Explicit proposal authorization updates only project evidence; runtime model settings, paid usage permissions and reviewer inheritance are unchanged.
- Add fixture-based tests for evidence freshness, observed availability, proposal/base integrity, atomic failure recovery and adapter parity. Preserve optional project catalogs on import/upgrade; no live model catalog ships with the template.


Queue-only cleanup with retained history. `/clean-queue old` archives DONE items completed
strictly more than 30 days ago; `/clean-queue all` archives every DONE item. READY/BLOCKED
items and trackers stay in place. The ninth shared procedure has a matching Codex adapter.

- The CLI supports `clean-queue old|all --dry-run|--apply`, with read-only preview and shared
  lock/revalidation for apply. No background cleanup or automatic commit/push.
- New queue completions record `completed_at` in UTC. Existing undated DONE items remain
  compatible: old reports/skips them, all can archive them. Never infer age from mtime.
- Each history snapshot retains original JSON bytes (including custom fields), SHA-256,
  archive timestamp and selection. Dependency and tracker validation resolve history;
  queue list/claims exclude it. `queue history [--id QNNNN]` browses retained snapshots,
  including after a mode downgrade. History is project-owned and has no expiry.
- Archive publication and filesystem sync precede source deletion. Identical leftover source
  copies are recovery state, not new work; retry finishes deletion. Changed duplicate IDs or
  damaged history fail validation. Batches are recoverable per item, not all-or-nothing.
- Update tooling, procedures/adapters and checks together before cleanup; old tools cannot
  resolve archived dependencies. Stop old-version workers and retain history in version control.

## 3.1.0

Explicit, record-preserving mode downgrades: `full -> tracker`, `tracker -> standard`, and
`full -> standard`. Use `downgrade <mode> --dry-run` for a read-only JSON report and `--apply`
for an atomic configuration change. Both report blockers; exit 2 means refused or blocked.

- Active leases block all downgrades. IN_PROGRESS, VALIDATING and REVIEWING trackers block
  standard mode. `--keep-pending` explicitly acknowledges paused queue items and, when moving
  to standard, PLANNED/BLOCKED/FAILED trackers. Records, IDs, evidence, expired leases,
  execution routing and project config extensions remain intact. No automatic DONE or deletion.
- Configure still refuses implicit downgrades. Upgrade validation checks retained records before
  publishing the higher mode; a DONE tracker with unfinished queue items must be reconciled
  before returning to full (reopen its tracker, or resolve its queue with real evidence).
- Configure, downgrade and worker operations share the queue lock, and worker mode checks run
  after acquiring it. Preview never creates a lock or expires claims; without an existing lock,
  its snapshot is advisory. Apply always locks and rechecks the current state.
- Templates still ship unconfigured standard/direct with no project records. Existing projects
  need no config migration; update tooling, docs and tests together and run their actual gate.

## 3.0.0

The reusable Claude/Codex extensions now ship in the template. This is a MAJOR because canonical authority, model/review policy and setup behavior change.

- AGENTS is the provider-neutral canonical contract; CLAUDE imports it. The project chooses ownership. Eight shared skills have eight Codex adapters, including init/gate parity. Scope/research/grill and Controller/worker procedures are portable; no product stack, primary provider or volatile model IDs ship.
- Config separates standard/tracker/full modes from direct/delegated execution. The fresh template is unconfigured standard/direct and contains no trackers, queue items or runtime leases. Unix mode/claim tooling preserves existing records and rejects implicit downgrades. Missing config prompts setup rather than silently skipping onboarding.
- Portable least-cost-capable model/effort selection replaces the historical strongest-reviewer mandate. Premium dispatch needs task-specific cheaper-option evidence; paid usage still requires authorization. HIGH independent review is mandatory even when a reviewer is unavailable (report BLOCKED).
- Structural checks cover both entrypoint imports, active canonical HIGH-review/model routing, both skill trees, eight adapters and relative targets. Git-visible Markdown scanning handles whitespace and excludes ignored dependencies. Before repair, seven new structure regression checks failed against the previous guard.
- Duplicate tracker IDs are rejected in tracker and full checks; FAILED is a valid tracker state. Before repair, duplicate-ID cases passed check and FAILED was rejected by the CLI; new regression tests demonstrate both. Mode/claim tests exercise temporary repositories, including stable request receipts, ownership and completion evidence.
- Workflow notice is preserved under `.lean/LICENSE`; root project licenses need not be overwritten on import. Current customizing/upgrade guidance replaces project-specific historical extension notes. Merge-debris ignore patterns remain, with lease/Python runtime exclusions added. Support is macOS/Linux/WSL (Bash, Git, Python 3.9+, Unix fcntl); native Windows and hosted/live runtime discovery are not claimed from local tests.
- CI runs ShellCheck, structure, hook tests, mode checks and Python regression tests. PROJECT gate matches these commands; application gates remain project-owned.
- Independent review caught two additional regressions before release: the installed smoke test assumed the host still had unconfigured template defaults, and completion allowed an unfinished dependency added after claim. Regression tests first failed on both. Smoke fixtures now isolate reusable assets and preserve configured hosts/licenses/records; completion rechecks current dependencies without losing a refused claim, and DONE dependencies are validated by check.

### Migrating from 2.x or local extensions

Before replacement, preserve existing CLAUDE/AGENTS additions, PROJECT, config, settings, records and local extensions. Move shared CLAUDE rules to AGENTS; make CLAUDE import it while preserving runtime-specific additions. Compare customized entrypoints rather than overwriting them. Keep configured tracker/full mode and all work records. If config has no execution field, direct is the compatibility default; projects with accepted mandatory delegation explicitly select delegated. Do not import another project's tasks or reset existing config to this template's unconfigured file.

Update shared skills and adapters, policy, hooks, tooling/templates/tests and workflow CI together; merge gitignore/settings and retain the workflow notice. Read CUSTOMIZING.md, fill actual project commands, run its Quality Gate and required independent review. Legacy CLAUDE authority is tolerated by the structure guard during migration; two competing contracts are not.

## 2.4.0

The Quality Gate tells a missing tool apart from a failing check. Both block; only one of them is
about the change.

- `quality-gate.sh` printed one verdict for every non-zero exit: `Quality Gate failed: <cmd>`, then
  "If your change caused this, fix it. If it was already failing or is outside the task, do not touch
  it: report BLOCKED and ask." Under that wording a command the shell never found reads as a check
  that ran and said no, so the agent reports `BLOCKED` over a diff with nothing wrong with it.
  Verified on the container Claude Code on the web runs in, which ships no `shellcheck` while
  `shellcheck` is the first gate command in this repository's `.lean/PROJECT.md`: exit 2,
  `shellcheck: command not found`, on every turn that touched a file.
- Exit 127 from a bare command name now reports `Quality Gate could not run: <cmd>` and names the
  tool, the environment, and the report it wants: `BLOCKED`, naming the gate command that could not
  run and the check the change is therefore unverified by. It still exits 2, and the skip cache and
  the `.claude/.gate-failed` marker treat it as the refusal it is. A message that let the turn finish
  would be the fail-open, not the fix: a gate that could not run has not passed.
- Three things have to hold before the gate blames the environment: exit 127, a lookup word that is a
  plain command name, and that name failing to resolve here. Each is there because the simpler rule
  before it was wrong about a shape a real gate block contains, and each was caught by review rather
  than reasoned out in advance. Shape alone was wrong for wrappers: 127 travels up from the program a
  wrapper ran, so `bash lint.sh` whose script calls a tool the diff never added exits 127 with bash
  plainly installed, and the first attempt called that an environment problem and named bash as the
  tool to install. The lookup alone was wrong for quoting: the `VAR=VALUE` strip is a regex over the
  line, so `FOO="a b" cmd` leaves `b"` as the word to look up, nothing resolves a fragment, and the
  wrapper case came back exculpated one quoted assignment later. And the status is not optional
  either: in `optional-linter ; pytest` the word that did not resolve is not the word that decided
  the verdict,
  so without that condition the excuse would bury a real test failure. It settles a compound line
  only when the deciding command's status is not 127; one that ends in 127 anyway is still
  attributed to its first word, which the paragraph below records.
- A word holding a slash names a file this repository points at, so a gate line whose script is
  missing stays an ordinary failure -- as does 126 (found, will not execute; usually an exec bit
  missing from the diff), and every other status. A word opening with a dash is an option, and an
  option is nobody's package to install: a gate command wrapped over two lines hands the extractor
  its continuation as a command of its own, and an indented `-x ...` reaches the shell as a command
  word and exits 127, so before the name had to start like a name the gate asked for `-x` to be
  installed. The same line unindented exits 2 instead, rejected as bash's own invocation option,
  which is why the case pinning this one is indented. Leading `VAR=VALUE` words are stepped over,
  or the verdict would turn on whether `CI=1` resolves as a command, which nothing does. Everything
  unclear
  takes the ordinary message, which sends the agent to look, because "not your change" is the verdict
  that can wave a real failure through.
- `test-hooks.sh` is now 55 checks. Three are the regression proper and fail against the 2.2.0 hook
  (2.3.0 left `quality-gate.sh` untouched, so that is the revision before this one):
  a missing program must say the gate could not run, must name the environment, and must not carry
  the "If your change caused this" line. The rest pin what must not move, one case per shape that got
  a condition wrong -- the wrapper, the quoted assignment, the compound line, the wrapped gate
  command's continuation, the script named by path, and a command that exists and fails -- and every
  term of the classification is pinned on its own: remove the status test, either half of the
  command-name test, the resolve test or the assignment strip and a check fails. The missing-tool
  branch is asserted to record the refusal the way the other branch does, with its fixture seeded
  first; without a cache to clear, the half of that assertion covering the cache passes whatever the
  hook does.

One fail-open this does not close: a gate command that swallows its own 127 still passes. `test -z
"$(gofmt -l .)"` with no `gofmt` prints the shell's complaint inside the substitution and then tests
an empty string, and that is the shape `.lean/PROJECT.md` recommends for formatters. A pipeline
masks it the same way, since the status is the last stage's. The hook reads the status of the command
it was given, and the status is 0. Judging the output instead would block a turn on any gate command
that merely prints those words, which in a downstream install is every turn,
so closing it needs its own evidence rather than a guess bolted onto this one. A related limit,
on attribution rather than on the verdict: when a compound line reaches 127 through a fallback --
`lean-optional || bash lint.sh`, where what is absent is the wrapper's own inner tool -- the excuse
attaches to the first word and can cover a check that did fail. It still blocks, and nothing outside
the command can say which stage produced the status.

**Upgrading:** no steps. The gate blocks the same states it blocked before; one of them now explains
itself differently.

## 2.3.0

`MODELS.md` has put the strongest model on `HIGH` risk review since the rule was written, and
nothing ever did it. `.claude/agents/reviewer.md` is `model: inherit` and no spawn site named a
model, so the rule was a no-op that announced nothing: a session on a fast model spawned a reviewer
on that same fast model for `HIGH` risk work, and the result reported review at `HIGH` depth --
true about the depth, silent about the reviewer. The evidence is structural and was checked on this
repository before the fix: `/lean-task` step 5, `/lean-review` step 4 and `CLAUDE.md`'s reviewer
line contained no mention of a model, and the new structure check below fails on all three of them
at the parent commit. For the absence half of that claim a scan is stronger than a run: no file
named a model, so the behavior could not have occurred. The enforcing half was run rather than
reasoned about -- this change's own `HIGH` review spawned the `reviewer` subagent with an explicit
model override, so the primary instruction is followable and not merely aspirational, and the
frontmatter's `model: inherit` is exactly what that spawn overrode.

- `/lean-review` step 4 and `/lean-task` step 5 spawn the reviewer on the strongest model available
  to the session. `CLAUDE.md` carries the same instruction, because it sends an agent to the
  reviewer without going through either skill -- the same reason it carries the round bound inline.
- Where the reviewer did not run on the strongest model available, the result says so. The report
  is conditioned on that outcome rather than on whether the model could be chosen: a session
  already running the strongest model inherits it and loses nothing, so reporting an inherited
  model as weaker would state something untrue. What is worth surfacing is the case this entry is
  about -- a reviewer no stronger than the author.
- `.claude/agents/reviewer.md` keeps `model: inherit`. Pinning the frontmatter would enforce the
  rule in one line and would break every install whose plan does not carry that model, in a
  repository whose whole purpose is to be copied into other projects. The frontmatter stays the
  fallback; the spawn site is where a model that depends on the session belongs.
- `.lean/scripts/check-structure.sh` fails if any of those three spawn sites stops naming the rule.
  A rule written in `policy/` and wired nowhere is exactly the failure above, and prose is the only
  place it can be wired, so a structural check is the only thing that holds it. The check reads the
  three known spawn sites by path and skips a file that no longer names the `reviewer` subagent in
  its code-span form: it is a gate command in every install, and the bare word is ordinary domain
  vocabulary, so guarding on it would block every turn in a project that dropped the bullet and
  writes about reviewers for any other reason. The anchor is the rule's phrase anywhere in the
  file rather than on the spawn line, because in `/lean-review` the two sit on different lines of
  wrapped prose: it catches the instruction being deleted, not a file that keeps the phrase
  elsewhere while dropping the instruction.

Review depth, risk rules, the round bound and the reviewer's own instructions are unchanged. MINOR
rather than MAJOR: the rule did not change, its enforcement did.

## 2.2.0

Review rounds are bounded. From this repository's own five-round run on one change, counted against
the branch rather than recalled: rounds 1 to 3 each returned `REWORK`, round 4 was the first
independent look at the regression fix and found seven things, round 5 found the fail-open described
below. One round followed a `PASS`, not two.

- A review cycle covers one Task Contract, and a change counts toward the cap when its motivation is
  a finding from that cycle's review. The most expensive round in that run came from taking on a
  second task mid-cycle: its new code introduced a regression that reopened the loop for the first
  task, and findings stopped mapping to a change. This rule separates the two, it does not shorten
  either.
- After the second `REWORK` on one contract, the cycle gets one last pass over the delta that fixes
  those findings, then stops. A capped cycle still holding a `REWORK` is `BLOCKED`, never `DONE`: a
  delta no reviewer has seen cannot satisfy condition 4 in `QUALITY.md`. Without that last pass a
  capped cycle would always ship its final fix unreviewed, and on this branch every round found
  something real in the previous round's fix, four times out of four.
- A `PASS` ends the review, and anything applied afterwards is new work with its own contract line.
  There is no carve-out for small fixes. Four were tried here and each one failed. "Cheap and clearly
  right" was unbounded, and on this branch that licence produced a real defect: round 4 passed, its
  seven advisory findings were applied, and one of them swapped a filesystem `grep -I` for
  `git grep -I`. Filesystem `grep` reads binary-ness from content; `git grep` honours
  `.gitattributes`, so a repository setting `*.md binary` skipped every markdown file while the scan
  reported clean -- a fail-open in a gate command every project runs on every turn. Round 5 caught
  it, and an unbounded rule means round 5 never happens, which makes this the rule that removes a
  round rather than the one above. Borrowing `WORKFLOW.md`'s trivial test failed the other way: it
  requires `LOW` risk and `CONTRACTS.md` makes every change inside a high-risk area `HIGH`, so it
  forbade fixing a typo in this file. "Comment or prose text" reopened the first hole, because the
  rules an agent follows are prose and `.lean/policy/` holds nothing else. Conditioning the prose
  half left the comment half: rewording the `<!-- gate:start -->` marker in `.lean/PROJECT.md` is a
  comment edit that turns the `Stop` hook into a silent no-op, verified. The carve-out went instead
  of gaining a fifth wording. What that costs depends on where the fix lands: where `WORKFLOW.md`'s
  trivial test can be met it is one contract line and no review, and inside a high-risk area it
  cannot be met at all, so a typo in one of these policy files costs a full `HIGH` cycle. That is the
  price of the area rather than of this rule -- the same price the borrowed trivial test charged --
  and it buys a rule with no wording left to argue with.

Run the corrected history through all three rules and the layout change is two `REWORK` rounds and
then a confirm pass, with the gate fix as its own short cycle. Round 3 found something real in round
2's fix, so that confirm pass plausibly returns `REWORK` too: three rounds ending `BLOCKED`, handed
to the user. That is the honest projection, not two rounds and done.

`REVIEW.md` has a `Rounds` section; `CLAUDE.md` carries both halves of the bound inline, because it
sends an agent to the `reviewer` subagent without going through the skill; `/lean-review` step 5
cites the section from the `PASS` and `REWORK` branches rather than restating it; `RECOVERY.md` lists
the capped case under `Blocked`, and `WORKFLOW.md` routes to the section. `QUALITY.md` condition 4
and `/lean-gate` now ask that review covered the delta that ships, not only that it ran at the right
depth -- `DONE` is decided on that path, and it does not read `REVIEW.md`. The round count goes in
the Result Contract's Evidence together with the range that review covered against the range that
ships, which `QUALITY.md` condition 4 now asks about. The pull request template prompts for both, so
they travel with the branch and a fresh session can recover them. Review depth is unchanged.

## 2.1.0

The Quality Gate no longer skips a turn just because the working tree is clean.

- `quality-gate.sh` decided whether to skip by asking whether the tree was dirty. Committing makes
  a tree clean, so an agent that changed files, committed them and ended its turn was never gated.
  That is the normal shape of a headless or CI run, and this hook is the only rule in the workflow
  that cannot be talked out of running. Verified before the fix, with a gate of `false`:
  uncommitted changes exited 2, the same changes committed exited 0.
- Skipping is now decided only by the recorded state, which already covered the commit, the
  uncommitted diff and untracked content. The clean-tree shortcut sat two lines above that
  comparison and returned before it was ever reached.
- `quality-gate.sh --seed` records the state and runs nothing; `session-start.sh` calls it. Without
  it, dropping the shortcut would make the gate run once per session even for a question that
  touched no files. If the SessionStart hook does not fire, the gate runs once at the first turn
  end rather than skipping -- the safe direction.
- A refused verdict now outlives the turn. A failing run records the state in
  `.claude/.gate-failed`, and seeding declines while that marker exists, so a new session cannot
  bless work the gate has already refused. Without it, seeding undid the fix after any SessionStart,
  and on a dirty broken tree it was worse than 2.0.0, which blocked. A passing run clears the
  marker. The marker is local state and gitignored, so it does not travel between checkouts and
  does not survive `git clean -xd`: after a clean, the next session starts with no memory of the
  refusal.
- `git ls-files --others -z | xargs -0 cat` in the state became a hazard once seed mode stopped
  draining stdin: with no untracked files, GNU xargs points the child's stdin at /dev/null but BSD
  xargs does not, so `cat` there would read the hook's own input. It is a read loop now.
- `check-structure.sh` gained three guards for this machinery: the gate's state files must be in
  `.gitignore` (otherwise each run's state includes the file the last run wrote and the gate never
  settles), `--seed` must not appear in `.claude/settings.json` (wiring it to Stop disables the gate
  in silence), and the retired-path scan now runs `git grep --untracked` rather than walking the
  working tree, so a vendored or ignored file naming a retired path cannot block a downstream
  project's every turn, while a new file a contributor has not staged yet is still covered. It
  matches text rather than references, so a project that owns a directory by either name should
  delete the check rather than satisfy it. `.gitignore` also covers `*.orig` and `*.rej` now: a
  conflicted merge of this very move is how such a file appears, and scanning untracked content
  would otherwise let it block the gate. The `.gitignore` entries are asked for by effect, via
  `git check-ignore`, so any equivalent pattern passes -- and both that and the scan need a git
  work tree, which the `npx degit` install route does not leave behind.
- `test-hooks.sh` is now 33 checks. Test 5 asserted "clean tree skips", which was the bug itself; it
  now asserts that committed work is gated. Every term of the state hash is covered: remove any one
  of the five and a check fails. Both guards that keep a refusal from being skipped are pinned
  separately, so removing either one fails a check even though the other would still hold.
  Restoring 2.0.0's clean-tree shortcut fails six.

**Upgrading to this from 2.0.0 or earlier:** if your Quality Gate currently fails, the first turn
after the upgrade will block, because the gate now runs on states it used to skip. `CLAUDE.md` tells
the agent not to repair a failure it did not cause, so it will report `BLOCKED` rather than fix it.
Clear the failure, or empty the gate block in `.lean/PROJECT.md`, before you start.

## 2.0.0

Every workflow path moved. Nothing about how work is done changed, but the versioning rule at the
top of this file was widened in the same commit: moving files an existing install depends on now
counts as MAJOR, which is what makes this 2.0.0 instead of a MINOR. An existing install needs the
migration steps below.

- `.agent/` is now `.lean/`: one namespace for the whole workflow, instead of rules in `.agent/`
  and self-checks in `.github/`.
- Self-checks left `.github/`, which now holds GitHub platform files only:
  - `.github/lean-workflow/check-structure.sh` -> `.lean/scripts/check-structure.sh`
  - `.github/lean-workflow/test-hooks.sh` -> `.lean/tests/test-hooks.sh`
- `check-structure.sh` gained three checks:
  - The scripts under `.lean/scripts/` and `.lean/tests/` are executable. This names a lost exec
    bit on `test-hooks.sh` instead of leaving it to CI. `check-structure.sh`'s own exec bit is not
    covered, because CI runs it by path and fails on permission before it can check anything.
  - The workflow version is present in both `.lean/README.md` and `.lean/CHANGELOG.md` and agrees.
    `.lean/PROJECT.md` is project-owned and free-form, so its version line is not read: a project
    whose own `PROJECT.md` says `Current version: 1.2.3` must not fail the workflow's checks.
  - `.agent/` and `.github/lean-workflow/` appear nowhere outside this file. Every text file is
    scanned, and the scan fails if it cannot complete rather than reading as clean. This check
    exists because the first attempt at this move left the root `README.md` pointing at both, and
    all three gate commands passed anyway -- the path check had just been repointed at the new
    namespace, so nothing was watching the old one.
- `CONTRIBUTING.md` and `.github/pull_request_template.md` added. The PR template is the Result
  Contract from `policy/CONTRACTS.md`, so the repository reports its own changes in the format it
  asks for.
- Zone names stay namespaced on purpose. A downstream project keeps its own `scripts/`, `tests/`,
  `docs/`, and root `CHANGELOG.md`, with nothing to rename and nothing to merge.
- Entries below describe the `.agent/` paths that were current when they were written. They are
  left as written.

### Migrating from 1.x

Run these **before** the `Upgrading` steps at the bottom of this file, not after. `git mv .agent
.lean` when `.lean` already exists does not fail: it nests the old tree at `.lean/.agent/`, your
`PROJECT.md` is no longer at `.lean/PROJECT.md`, and the `Stop` hook then silently does nothing,
because a missing `PROJECT.md` is a no-op by design.

1. `git mv .agent .lean`
2. `mkdir -p .lean/scripts .lean/tests`, then `git mv` `check-structure.sh` into `.lean/scripts/`
   and `test-hooks.sh` into `.lean/tests/`. Remove the empty `.github/lean-workflow/`.
3. Take the workflow-owned files from the 2.0.0 release instead of editing them; they already use
   the new paths. That is `.lean/README.md`, `.lean/CHANGELOG.md`, `.lean/policy/`,
   `.lean/scripts/`, `.lean/tests/`, `.claude/hooks/`, `.claude/skills/lean-*/`,
   `.claude/agents/reviewer.md`, and everything in `CLAUDE.md` above `## Project additions`.
   Also `AGENTS.md`, unless you edited it. If you edited any of the others, diff before
   overwriting. `.claude/settings.json` is not in this list: it names no retired path, and
   `Upgrading` step 6 has you merge it by hand.
4. Edit only what is yours. In `.lean/PROJECT.md` replace `.agent/` with `.lean/` and repoint the
   two script paths, including the ones inside its Quality Gate block. Do the same in your own
   `README.md` and any project file that named them.
5. Update `.github/workflows/lean-workflow.yml`: the two script paths, the `shellcheck` glob, and
   the `paths:` filters.
6. Confirm nothing was left behind, then validate:
   - `git grep -l -e '[.]agent/' -e '[.]github/lean-workflow/'` should list nothing but this file.
   - `ls .lean/.agent` should say no such directory.
   - `.lean/scripts/check-structure.sh` and `.lean/tests/test-hooks.sh` should both pass.

## 1.4.0

Changes from dogfooding (a Go CLI, 5 headless runs). The Task Contract was never written, `TESTING.md` was never read, and policy files were rarely opened outside skills. Rules that work are the ones in `CLAUDE.md` and the hooks.

- `CLAUDE.md` now carries the critical rules inline:
  - a one-line contract as the first line before changing files;
  - regression tests for bug fixes, shown failing before the fix and passing after;
  - no reading of workflow internals unless the task needs them.
- The Task Contract is one line at every risk and quality level. In round 2 the one-liner was written in 4/4 runs; the full block added nothing.
- `/lean-task` is shorter and loads policy files only when needed.
- Gate failures: fix only what your change caused. Pre-existing or out-of-scope failures are reported as `BLOCKED`, never patched under hook pressure. In round 2 the Stop hook pushed Claude into editing an unrelated test file.
- Gate commands must exit non-zero on failure. `/lean-init` and `PROJECT.md` say so, with the `gofmt` example.
- README note on headless and CI use.

## 1.3.0

- Self-checks for the workflow files in `.github/lean-workflow/`:
  - `test-hooks.sh` — Quality Gate and SessionStart hook behavior in throwaway git repos.
  - `check-structure.sh` — referenced paths exist, settings valid, hooks executable, skill/agent frontmatter, gate markers.
- CI `.github/workflows/lean-workflow.yml` runs ShellCheck and both scripts when workflow files change.

## 1.2.0

- Policy files moved to `.agent/policy/`. `.agent/PROJECT.md` stays as the only project-owned file, so upgrades can replace `policy/` as a whole.

## 1.1.0

- Claude-native layer in `.claude/`, pointing into `.agent/` with no rule duplication:
  - `reviewer` subagent for independent `HIGH` review.
  - Skills: `/lean-init`, `/lean-task`, `/lean-review`, `/lean-gate`.
  - `SessionStart` hook suggests `/lean-init` while `PROJECT.md` is empty.
  - Permissions: allow read-only git commands, deny reading `.env` files.

## 1.0.0

- Baseline #1: Task Contract, Quality Gate, risk-based testing and review, progressive context.
- `CLAUDE.md` canonical, `AGENTS.md` adapter.
- Defaults for quality, budget, and risk.
- `Stop` hook Quality Gate driven by `PROJECT.md`.

## Upgrading

Read the target release's migration entry first, especially when crossing a MAJOR. Current import/upgrade authority is documented in `.lean/CUSTOMIZING.md`; historical entries above describe the arrangements at that time.

1. Preserve project-owned PROJECT/config, records, local extensions and entrypoint additions.
2. Upgrade policy/router/changelog, all shared skills and Codex adapters, hooks/reviewer, templates, tooling and installed self-tests together.
3. Merge settings/gitignore/CI rather than replacing project permissions or application checks. Retain `.lean/LICENSE` and existing project licenses.
4. Reconcile canonical ownership and project overrides explicitly; never silently reset mode, execution or primary agent.
5. Run the actual project Quality Gate and workflow tests that remain installed. Complete required review over the final delta before reporting DONE.
