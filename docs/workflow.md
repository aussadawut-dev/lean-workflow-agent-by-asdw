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

## Archive and resume

`lean tracker archive --dry-run|--apply` moves DONE trackers to `docs/history/agent-workflow/`; their IDs stay reserved. `lean mode context` prints a read-only summary (mode, active tracker and its next step, claims, Git status, last gate result, progress) for resuming after a break or a new session.

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
