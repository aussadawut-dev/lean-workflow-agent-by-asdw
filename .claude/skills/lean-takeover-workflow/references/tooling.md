# Takeover tooling

Run the trusted baseline's `.lean/scripts/takeover.py`; never execute discovered target scripts during audit. Python 3.9+ and Unix `fcntl` are required. The tool writes UTF-8 text and normal permission bits, not arbitrary binary migrations, ownership/ACL changes, directory moves, symlinks or global runtime configuration. Filesystem discovery is a starting inventory, not a guarantee that every workflow dependency has been found.

## Session and full-read evidence

```sh
python3 .lean/scripts/takeover.py inventory "/path/to/target" --session "/private/path/takeover-session"
python3 .lean/scripts/takeover.py include --session "/private/path/takeover-session" --path src/workflow-helper.py
python3 .lean/scripts/takeover.py cover --session "/private/path/takeover-session" --path AGENTS.md --evidence <fully-read-sha256>
python3 .lean/scripts/takeover.py exclude --session "/private/path/takeover-session" --path docs/product.md --evidence "Product prose outside agent workflow; no workflow references"
python3 .lean/scripts/takeover.py draft --session "/private/path/takeover-session" --baseline "/path/to/trusted/lean"
```

`inventory` enumerates tracked, untracked and known runtime files without changing the target, records safe candidates' hashes, and writes an empty plan. It does not run Git hooks, target code or remote tools. Full-read coverage is an explicit operator attestation after seeing complete content; exclusions are visible and reviewed. Follow references and use `include` for missed files. Protected paths cannot be promoted. A nested repo, inaccessible required file or private configuration that affects behavior requires a scoped resolution rather than a fake coverage pass.

`draft` imports only the portable assets explicitly declared in the baseline’s `.lean/assets.json` release registry and stripped root entrypoints. Adjacent unregistered local scripts/templates are excluded. Upgrade a pre-registry baseline before using this helper. PROJECT, config, settings/permissions, gitignore, CI/PR templates and source user guides are deliberately left for target-specific reconciliation. It adds an unresolved item so it cannot be applied directly. It preserves an already populated plan rather than replacing edits. It fingerprints every portable source file. The tool does not synthesize rules, decide which old behavior to drop, or infer user authorization.

## Plan format

Edit the external session's `plan.json` from its generated draft. Keep `schema`, `id`, `target` and baseline fingerprints intact. See the [plan template](../../../../.lean/templates/takeover-plan.json). The arrays have these meanings:

- `decisions`: `{id, choice, evidence}`. Record actual user answers or already accepted decisions, never invented consent. Routine mechanics need no decision record.
- `unresolved`: material blockers; must be empty before sealing.
- `acceptance`: nonempty observable checks, including preservation and review criteria.
- `dispositions`: `{path, action, reason}` for every fully read file. Actions: `keep`, `replace`, `migrate`, `retire`. Include documentation routes and ID mappings in reasons or companion session evidence where needed.
- `rule_map`: `{source, rule, destination, reason}` for requirements/decisions whose meaning must survive or explicitly change. File dispositions alone do not prove semantic preservation.
- `operations`: `{path, before, content, mode, reason}`. `before` is the inventory's `{sha256, mode}` or `null` for a new file. `content` is the exact resulting UTF-8 text or `null` for deletion; `mode` is an integer of ordinary permission bits (420 = 0644, 493 = 0755). Paths are relative POSIX paths inside the target. A move is a destination write and source deletion; snapshot both. Do not put references to mutable external payload files in the plan.

Review each operation against the target original, not just the baseline draft. Preserve dirty originals. `keep` contradicts a write; existing Lean trackers/queue records cannot be changed by this writer. Mode lowering, claims and record state transitions retain their existing workflow guards. Supported foreign-record conversions use `record_migrations` below; they need full-read coverage, rules/ID mapping and an accepted decision before adding exact operations.

## Explicit foreign record mappings

Tracking README/TEMPLATE, queue README and the queue schema are support documents, not task records; ordinary reviewed operations may reconcile them. Other existing records retain the guard.

`record_migrations` is optional; omitting it retains the original record guard. The supported format is `casetodian-v1`, recognized by queue `workset`/`task`/`objective` without Lean's `tracker`, or a tracker with `## Tasks` or `## Tasks and queue mapping` whose status/evidence shape is foreign. An exact native Lean Status line together with `## Evidence` remains protected. This is a format adapter, not permission to rewrite valid Lean records or invent missing states.

```json
{"source": ".agents/queue/items/Q0389.json", "archive": "docs/history/agent-workflow/Q0389.txt", "format": "casetodian-v1", "kind": "queue", "decision": "accepted-record-transition"}
```

For every mapping, add both operations: a new archive with exact original UTF-8 bytes and permission bits, ordered before the source replacement/deletion. The archive is inert `.txt` under `docs/history/agent-workflow/`. Link the mapping's `decision` to an actual accepted decision in the plan. Existing read coverage, disposition, rule map, drift checks, approval, snapshot, journal and rollback rules still apply.

Queue mappings preserve ID, title, workset as `tracker`, dependencies and exclusiveScopes as `scopes`. Keep the entire original object in `legacy`. Map TODO to READY; retain BLOCKED and DONE. DONE `evidence` is the original completion evidence joined with newlines; copy recorded createdAt/completion.completedAt to created_at/completed_at when present, never infer timestamps. Pending evidence is null. Other normalized fields are rejected.

CANCELLED is deleted from the active queue only after its exact original is written to `.agents/queue/retired/<ID>.txt`. Lean validates cancellation history and rejects reusing its ID in active items or DONE history. Cancelled records do not satisfy DONE dependencies and are never converted to DONE. Preserve original reasons and tracker task mappings in historical documentation.

Tracker mappings use `kind: "tracker"` and an explicit `status`; TODO maps to PLANNED and REVIEW to REVIEWING. All original Status declarations must agree by default. An explicitly accepted resolution may use `status_decision` to reference a plan decision whose `record_statuses` object maps that exact source path to the selected status. Absent states still block conversion. Keep contradictory historical statements in the exact original and preserve their limitations in the normalized record. The normalized tracker must have one canonical Status line and a route to its exact original archive. Preserve accepted scope, owners, task/queue IDs, evidence and limitations through the reviewed mapping; the tool does not infer these from prose. For DONE, mapping `evidence` is a nonempty array of exact nonblank source lines from Validation, Validation evidence, Validation plan and evidence, Validation and acceptance, Acceptance, Acceptance and evidence, Acceptance and validation, Evidence, Evidence and review, Execution snapshot, Impact and validation, or Validation and handoff sections. Normalize `## Evidence` to exactly those lines, each prefixed with `- ` and ending in a newline. Empty or unsourced evidence blocks conversion; an old DONE label alone does not prove completion. Other states may omit evidence, but any normalized evidence must follow the same source-bound rule. A later tracker may supply publication evidence only when `evidence_source` names another fully read tracker mapping with an exact archived original, and the same accepted status decision maps the child path to that parent path in `record_evidence_sources`. Evidence remains exact source lines; retain waivers and NOT_RUN limits and identify the parent source in the reviewed normalized document. This does not automatically close tasks or prove waived criteria.

A closed foreign tracker with no linked queue may instead use `historical_only: true` and `history_decision`. That accepted decision must list the exact source path in `archived_trackers`; status must be DONE and the source operation must delete the active file after writing its exact inert original. This preserves historical exceptions without inventing queue IDs or weakening new Full-mode rules. Keep a history index and update document routes in the reviewed plan. Native Lean records remain protected. A tracker still referenced by queue items cannot disappear: staged full record validation rejects the missing tracker.

`stage-check`, `seal`, and apply/resume additionally run trusted Lean full record validation on staged mapped records. Missing trackers, unfinished DONE dependencies, unsupported states or invalid completion evidence block sealing regardless of a claimed passing stage-check string. Target application validation and independent HIGH semantic review remain required.

## Approval, apply and recovery

```sh
python3 .lean/scripts/takeover.py check --session "/private/path/takeover-session"
python3 .lean/scripts/takeover.py stage --session "/private/path/takeover-session"
# Run safe deterministic workflow checks in the returned staging directory.
python3 .lean/scripts/takeover.py stage-check --session "/private/path/takeover-session" --evidence "Passed commands/results and staged coverage limits"
python3 .lean/scripts/takeover.py seal --session "/private/path/takeover-session" --evidence "User accepted plan <id> and the presented diff in this conversation"
python3 .lean/scripts/takeover.py apply --session "/private/path/takeover-session" --approval <sealed-plan-sha256>
python3 .lean/scripts/takeover.py status --session "/private/path/takeover-session"
python3 .lean/scripts/takeover.py resume --session "/private/path/takeover-session" --approval <same-sealed-plan-sha256>
python3 .lean/scripts/takeover.py rollback --session "/private/path/takeover-session"
```

`seal` records matching user approval, not a request for it. Neither `check` nor `seal` changes target files. The CLI cannot authenticate a human answer; the skill owns that boundary. Changes to plan, inventory or staged validation evidence invalidate the receipt. `stage` materializes fully read public files and exact final operations outside the target; it does not copy secrets, generated dependencies or unrelated app files. Run the safe workflow checks there (initialize Git there if needed), record actual results using `stage-check`, and retain the actual target gate after apply. Staging may be regenerated before approval, clearing prior validation; after sealing it is immutable. The tool checks staged content/mode fingerprints and unreviewed workflow paths, while the agent owns truthful command-result evidence. Apply also verifies the staged result. It checks source revisions, audited target revisions/file set, operation preconditions, symlink boundaries and active Lean claims. Untracked and dirty files are handled identically to tracked files; no Git reset/commit is used.

Apply creates `.agent-runtime/queue.lock` for local coordination; it may persist after failure/rollback. The reviewed gitignore must ignore runtime state. Snapshots and the journal remain in the private external session with original bytes and permission bits. Do not delete the session while recovery may be needed. After all writes, status is APPLIED pending the target's gate and HIGH independent review. Running apply again with the same receipt verifies the completed state and performs no repeated writes. A fresh takeover of an identical installation should propose no changes after project reconciliation.

Resume tolerates a crash between an intended write and its completion receipt, but blocks unexpected revisions. Rollback preflights all started operations, verifies snapshot checksums, restores only before/after states belonging to this journal, and removes empty directories created by these operations. It refuses to overwrite subsequent edits; preserve those edits and resolve the recovery conflict explicitly. Interrupted rollback resumes by calling rollback again. Rollback does not require the baseline repository to remain available. Session contents are local trusted recovery data; do not hand-edit journals or receipts.

The tool never reports DONE or runs target gates automatically. A blocked apply can leave a recoverable partial migration; report status and affected paths. Foreign workers and noncooperating manual edits are outside the queue lock's protection. Complete semantic validation and review through the shared skill.
