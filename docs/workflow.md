# Workflow, modes, trackers and queue

[Back to README](../README.md)

## Phases

```
contract -> scope -> implement -> test -> validate -> review -> gate -> done
```

Each phase is a seventh of the progress bar; `--done N --total M` fills the current phase. The rules for each phase live in [.lean/policy/WORKFLOW.md](../.lean/policy/WORKFLOW.md); `/lean-task` walks them in order. The [workflow map](workflow-map.md) draws every branch as a flowchart.

```sh
python3 .lean/bin/lean progress set implement --done 2 --total 5 --task "add login"
# ███████░░░░░░░░░░░░░ 34% implement 2/5 — add login
```

## Measure and explain work

Use the local activity log to find repeat checks and expensive phases before
changing the workflow. Task and session filters apply to all attributed events;
old events without that attribution remain visible in the unfiltered log.

```sh
python3 .lean/bin/lean log --summary
python3 .lean/bin/lean log --task "add login" --session SESSION_ID --summary
python3 .lean/bin/lean log --json
python3 .lean/bin/lean plan --explain
python3 .lean/bin/lean plan --tier stop --json
```

Activity includes individual workflow gate checks and test files as well as their
parent runs. Their durations overlap: a test can run inside a gate check and test
files can run in parallel. Do not add these categories to estimate elapsed work
time. Phase intervals can include human idle time. Token usage is unknown when no
usage observation is available; the log does not estimate subscription cost.
Logging is best effort and local, so missing observations are not zero cost and
the log never serves as acceptance evidence.

`lean plan` is a read-only preview of the existing selection rules and configured
gate commands. `--base COMMIT` adds workflow changes since that commit;
`--contract 'Contract: ...'` supplies the review floor, and `--session ID` selects
the session whose context is inspected. `--json` returns structured output.
Application target commands and roots are reported separately: Lean's own impact
map cannot select an application's tests. Undefined checks and unassessed reuse
conditions stay explicit. An explicit Stop tier needs its own gate block;
automatic Stop hooks choose the full tier when that block is absent.

The preview runs no checks, accepts no control changes and records no PASS.
Recheck the actual gate after editing: a preview is an observation, not a promise
that its inputs will remain unchanged. These commands work through the shared CLI
for Claude, Codex and agy. They do not enable per-check caching or model routing.

## Modes

| Mode | Keeps | Commands |
|---|---|---|
| `standard` | Evidence in the conversation | — |
| `tracker` | One `docs/tracking/TCKNNN[-slug].md` per non-trivial workset | `lean tracker new --id TCK001 --title "..."`, `lean tracker status --id TCK001 --status DONE --evidence "..."` |
| `full` | Tracker plus `.agents/queue/items/QNNNN.json` with lease claims | `lean queue list`, `claim`, `claim-next`, `heartbeat`, `complete`, `release` |

A tracker cannot become DONE while any acceptance criterion or task checkbox is unchecked or its Evidence section is empty. In full mode, a DONE tracker also needs every linked queue item DONE.

Upgrades (`standard -> tracker -> full`) keep every record. Downgrades are explicit: `lean mode downgrade <mode> --dry-run`, then `--apply` (`--keep-pending` to pause unfinished work). Active claims block any downgrade; in-progress trackers block `standard`.

## Queue leases (full mode)

Claims last 30 minutes. A worker claims with a stable random request ID and retries with the same ID after a lost response; it gets the same token. Only the token holder heartbeats, completes or releases. Completion needs evidence and DONE dependencies. Dependencies and exclusive scopes decide what `claim-next` hands out; one agent holds one claim at a time.

Scopes without a colon are relative repository paths. Claims conflict when the paths are equal or one contains the other: `src/` conflicts with `src/a.ts`, while `src` and `src-other` remain separate. Path comparison normalizes separators, `.` and internal `..` lexically; it does not inspect the filesystem, follow symlinks or fold case. `src` and `src/` name the same scope, and `.` covers the repository. Absolute paths, paths escaping the repository, empty paths and wildcard path scopes are refused. Use concrete paths instead of globs. This validation also applies when retained queue records and active leases are loaded.

Colon namespace labels such as `area:api` remain opaque and conflict only with that exact label. They do not implicitly own any path; workers sharing files must use overlapping path scopes or the same agreed label. Windows drive-root paths are absolute paths, not namespace labels. A path scope is an ownership declaration, not a filesystem access boundary.

## Archive and resume

`lean tracker archive --dry-run|--apply` moves DONE trackers to `docs/history/agent-workflow/`; their IDs stay reserved. `lean mode context` prints a read-only summary (mode, active tracker and its next step, claims, Git status, last gate result, progress) for resuming after a break or a new session.

For a smaller handoff, use `lean mode context --compact --tracker TCK001`.
The compact report includes source paths and a content digest observed when it
was generated, the selected tracker's unresolved acceptance, decisions and next
action. It is a sourced snapshot, not a new memory store or a validation result.
Regenerate it after source changes. The gate field still reports the current
shared evidence status, which can be stale even when the context was just read.

`--max-chars N` sets the compact output budget (default 6000 characters).
Optional text may be truncated with an explicit indication. If mandatory
acceptance/next-action content cannot fit, the command fails with a source
reference instead of silently dropping obligations; increase the budget or read
the tracker. With several unfinished trackers, choose one using `--tracker`.
The original `lean mode context` JSON remains available without `--compact`.

## Optional intake and bounded batches (all modes)

Use `lean intake` when a workset receives continuing requirements. It adds a durable
ledger without requiring full mode or leases. Classify each message: clarification
of current acceptance; bug blocking acceptance; user direction replacing old work;
or new feature queued for later. The model checks ambiguity/conflicts and proposes
priority/dependencies; the user decides material trade-offs. Feature approval does
not mean immediate interruption.

```sh
python3 .lean/bin/lean intake add --id R1 --kind feature --text "Export results" --task TASK-01 --acceptance "Export contains selected rows"
python3 .lean/bin/lean intake list
python3 .lean/bin/lean batch start --id B1 --controller codex --requirements R1
python3 .lean/bin/lean batch freeze --id B1 --contract 'Contract: risk=MEDIUM quality=HIGH acceptance=export contains selected rows'
python3 .lean/bin/lean batch readiness --id B1
```

`intake add` always queues entries and requires task/acceptance traceability. Use
repeatable `--depends ID`; a direction may use repeatable `--supersedes ID` for
queued requirements. `intake cancel --id ID --reason TEXT` retains a queued entry.
A task reference is a required descriptive ID, not a claim that Lean has verified
its implementation or acceptance. `intake check` and `mode check` validate the
ledger's references, cycles, completeness and primary ownership. Existing projects
without a ledger remain unchanged. The ledger is a Markdown tracker record named
`INTAKE.md` directly in the tracking directory; its JSON block is managed by the CLI.

Selection is explicit: user priority, acceptance blockers, dependency order,
finish current work, then next feature. `list` shows intake order, not an invented
priority score. `batch start` refuses unresolved external dependencies and multiple
primary batches for one Controller. Workers may still implement subtasks of that
batch; this is separate from full-mode lease ownership.

For an explicit interruption use `batch checkpoint --id B1 --reason TEXT`, then
start the new batch. Paused work retains its requirements; `batch resume --id B1`
reclaims the Controller slot. A checkpoint is not completion and does not satisfy
dependencies. A frozen batch must be reopened before checkpointing.

Freeze only after implementation and deterministic validation are ready for review.
It snapshots the requirements and exact Task Contract. New intake stays queued;
fix review findings within that scope. To change direction use `batch reopen --id B1
--reason TEXT`, then `batch scope --id B1 --requirements R2 --reason TEXT`. The latter
returns removed requirements to the queue; supersede/cancel them explicitly so they
remain traceable. Reopening invalidates batch readiness and requires a **new contract**
before another freeze, even if the shipping bytes have not changed. No automatic
permission prompt is added for ordinary clarification or fixes within acceptance.

Readiness reports implementation, review and gate separately. Implementation READY
means the Controller declared it ready by freezing; it is not proof of acceptance.
Review uses the existing whole-checkout receipt. Below HIGH depth,
`batch review --id B1 --evidence TEXT` records a semantic-review attestation bound to
the shipping content; HIGH depth still requires the independent reviewer and receipt.
Content changes invalidate review through the existing fingerprint mechanism.
Gate NOT_RUN/deferred, STALE, FAIL and PASS remain distinct. A deferred gate does not
make implementation incomplete and cannot permit closure. This command never runs
the gate or changes its automation preference.

After acceptance is evidenced in the owning tracker, current review and gate PASS
allow `batch finish --id B1`. Closed requirements remain active in the requirement
lifecycle (accepted, not superseded/cancelled); the closed batch records completion
and satisfies dependencies. Tracker records are excluded from semantic review by
existing policy; the ledger is an **attestation**, not tamper-resistant evidence.
Updating it can stale the gate cache, so synchronize tracker/closure records before
the final shared gate. Review/gate coverage is always the whole shipping checkout;
this feature does not isolate unrelated checkout changes or enforce use through
hooks. Hook activation, portable evidence and machine/environment diagnostics are
separate follow-ups.

If the user cancels or replaces the entire batch, reopen it if frozen, then use
`batch retire --id B1 --reason TEXT`. This releases ownership and returns all
requirements to the queue so they can be cancelled/superseded explicitly. Retirement
retains the batch history and never satisfies dependencies or claims completion.

For selected targets, the ledger follows `record_root` while review receipts,
shipping fingerprints and the shared gate use `workflow_root`, including application
submodule contents. Normal CLI routing supplies both; an explicit external record
root must be paired with `--workflow-root`. Target intake ledgers receive the same
semantic-review exclusion as the workspace intake tracker, avoiding self-invalidation
when recording review or closure; the gate still fingerprints their final bytes.
Read-only intake/list/check/readiness commands inspect an atomic snapshot without
creating runtime directories or lock files.
