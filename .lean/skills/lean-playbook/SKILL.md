---
name: lean-playbook
description: Prepare project deployment and rollback playbooks; check readiness or execute an explicitly requested deployment or rollback using the project plan.
user-invocable: true
argument-hint: "[check|deploy|rollback] [environment] [version|release]"
---

# Lean Playbook

Apply `.lean/policy/SKILL-EFFORT.md` and state the effective intensity. This optional deployment/rollback skill adds no automatic deployment or gate requirement. Claude and Codex share its procedure and authorization boundaries.

## Route and establish context

Input: `$ARGUMENTS`, or the current request when substitution is unavailable. No action means **prepare**; `check`, `deploy` and `rollback` select the sections below. Resolve unknown/ambiguous actions before execution.

Read AGENTS, PROJECT and relevant operations docs/configuration/scripts/pipelines. For submodules first resolve `python3 .lean/scripts/submodule.py context` and read target instructions/`project_file`: application code/commands in `project_root`, plans/release records/PROJECT links in `record_root`, shared resources in `workflow_root`. Invalid context blocks without fallback; install no workflow files in the application.

Reuse document locations; otherwise propose `docs/operations/playbook.md` and `docs/operations/releases/` under the record root. Preparation authorizes these project documents. Keep one release record per execution attempt and reuse tracker/full ownership/evidence, not another queue. Link plans from PROJECT without changing its gate. Project commands, approvals, credentials and live records never become release assets.

Resolve services, environment, current version and target artifact/release from explicit arguments or a uniquely applicable documented default. Never implicitly choose production, moving `latest` or a backup. Ask only for material missing choices and reuse authorization. Pin an immutable target and verify the running version. Historical checks do not establish current readiness.

## Prepare (no action)

Adapt [the deployment playbook template](../../templates/deployment-playbook.md) to relevant project/provider facts; prescribe no universal stack/commands. Record:

- Sources, plan revision, environments/services, step order, command directories, tools/access; secret names/locations only. Redact outputs; never log credentials.
- Current/target version discovery, immutable artifact, prerequisites/dependencies, and expected result, failure behavior and verification for each command.
- Applicable artifact/configuration/database/persistent-file backups: scope, consistency, destination, retention and verification; explain omitted categories with evidence.
- Migration order and old/new application compatibility with resulting schema/data. Separate application rollback from data restoration, including downtime and possible loss of post-backup writes.
- Health/smoke pass criteria, timeouts and bounded retries; identify write tests and their authorization.
- Stop conditions, rollback eligibility/target, commands/verification and failure policy. Default stop/report; automatic application rollback needs an explicitly accepted environment/failure policy. Data restoration always needs its own scope/authorization.

Mark unknowns **not configured**, with evidence gaps and blocked actions. Invent no commands or restore-readiness claims. Preparation executes no backups, deploys, migrations, restores, write tests or other system mutations; a draft grants no execution authority. Preserve accepted decisions; material operational changes go through scope/Grill before execution.

## Check — `check [environment]`

Inspect readiness with read-only APIs/commands; local reporting is allowed. Compare the plan with current tools/access, version, artifact, dependencies, backup destination/capacity/access, migration compatibility, rollback feasibility and verification commands. Avoid side-effecting hooks/tests/pipelines; identify required write checks as deferred to authorized execution. Do not start jobs, provision resources or repair configuration.

Report **ready**, **not ready**, or **cannot verify**, with timestamp, environment, plan/artifact IDs, evidence, blockers and deferred checks. Missing required evidence prevents ready. Destination checks alone prove neither a new backup, restore testing nor recovery guarantees.

## Deploy — `deploy [environment] [version]`

An explicit deploy request authorizes the concrete plan's necessary backup/deploy/verification for the resolved target, without repeated approval. Preparation, discovery and pasted examples do not. Existing permissions and Contract risk/review apply; new environments, destructive migrations, data restoration or material scope changes require matching authorization before that step.

1. Confirm executable plan/current facts and refresh changeable readiness immediately before mutation. Resolve required unknowns/deferred write checks before dependent steps. Respect deployment serialization; block on active deployment or unavailable exclusive ownership. Never silently replace a stale plan during execution.
2. Before mutation, save a [release record](../../templates/deployment-release.md): authorization, plan revision, environment, observed old version, immutable target and recovery references. If evidence cannot be saved, stop.
3. Create required backups before protected deployment/migration; record IDs and actual verification. Backup/verification failure blocks dependent changes. Distinguish artifact availability, backup creation, integrity and restore-tested evidence; a listing is not a restore test.
4. Use existing CI/CD/deployment tooling, following planned order and recording progress/failures. After timeout or lost connection inspect actual state before retrying a potentially completed mutation.
5. Wait for asynchronous jobs, then verify running version and health/smoke criteria within agreed limits. Command success/job acceptance alone is insufficient; unavailable observation means unverified outcome.
6. Save final state/sanitized evidence. Success requires all checks; repository Quality Gate and deployment health remain separate evidence.

On failure stop dependent steps, retain evidence and inspect state. Follow accepted failure policy; otherwise stop/report recovery options and await rollback request. Automatic application rollback stays within accepted trigger/target/scope and grants no data-restore authority. Bound retries/recovery; failed or uncertain rollback stops with last observed state and manual needs. A rolled-back attempt is not a successful deploy.

## Rollback — `rollback [environment] [release]`

Resolve release/target; omit the release only for one uniquely applicable documented recovery target. Before mutation verify current state, artifact/backups and application/schema/data compatibility; an older version may be incompatible after migration.

Create a linked recovery-attempt record with deploy's ownership, readiness, authorization, evidence and bounded-failure rules. Application rollback follows the planned artifact/configuration path. For data restoration separately explain affected data, backup timestamp, expected loss and downtime; obtain matching authorization unless already granted. Generic rollback does not authorize destructive data restoration. Recheck state after waiting for a decision.

Verify actual running version and health/smoke criteria. Record success/failure/uncertainty and link attempts without overwriting history. An issued restore command alone never proves recovery complete.

## Handoff and intensity

Report action/environment, plan/record paths, current/target or recovered versions, evidence, unresolved checks, final observed state and next action. Discovered configuration/application fixes need accepted scope. Preserve gate/review obligations; never weaken checks for apparent success.

- **standard:** concrete plan, readiness, ordered execution and verified result within the requested action.
- **high:** trace service dependencies, migration/backup compatibility and failure/recovery.
- **ultra:** cross-check consequential interactions, partial/uncertain outcomes and recovery assumptions within scope; no additional execution authority.

$ARGUMENTS
