# Deployment and rollback playbook

Project-owned plan. Adapt to existing operations documents; remove irrelevant fields with a reason. Missing required facts are **not configured** and block the affected action. This template grants no execution authority and contains no runnable deployment defaults.

- Application/services and owner:
- Plan revision/date and source configuration/pipeline references:
- Environment(s), target identity and explicit defaults (if any):
- Tools, access and secret references (never secret values):
- Version discovery, immutable artifact selection and provenance:
- Deployment ownership/serialization and concurrent-operation detection:
- Dependencies, downtime/maintenance requirements:

## Readiness

| Check | Read-only command/API and working directory | Expected result | Blocker or deferred write check |
|---|---|---|---|

## Backup and recovery compatibility

| Scope (artifact/config/database/files) | Method and consistency | Destination/reference and retention | Verification and failure rule |
|---|---|---|---|

- Migration order and old/new app compatibility with resulting schema/data:
- Recovery target selection and artifact/backup availability:
- Restore procedure, downtime and possible loss of writes since backup:
- Evidence required for backup creation, integrity and restore-tested claims:
- Data-restore authorization scope (separate from application rollback):

## Deployment steps

| Order | Command/pipeline and working directory | Expected result/evidence | Timeout/retry limit | Failure or uncertain-outcome action |
|---|---|---|---|---|

## Verification

| Running-version/health/smoke check | Command/API | Pass criteria | Timeout/retry limit | Side effects and authorization |
|---|---|---|---|---|

## Failure policy and rollback

- Default: stop/report. Any accepted automatic application rollback policy: decision reference, environment, trigger, target and limits:
- Stop conditions, recovery prerequisites and incompatible migrations:

| Order | Application rollback command and working directory | Expected result/verification | Failure or uncertain-outcome action |
|---|---|---|---|

- Separate data restoration steps and matching authorization, if applicable:
- Escalation/manual recovery route and evidence to preserve:
- Release record location:
- Open decisions / not configured facts, evidence gaps and blocked actions:
