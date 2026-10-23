# Isolated local deployment and rollback experiment

Procedure: lean-playbook, standard intensity, for current dirty. Lean 4.7.0 has no
lean-playbook skill; its infrastructure smoke uses this same externally supplied plan.
This is not an autonomous agent evaluation of either version's deployment decisions.
Authorization: user requested local deploy/rollback tests, authorized test credentials,
sequential version execution, and removal of the experimental submodule after results.

## Releases and compatibility

- A: Casetodian 7f76ac426784c3665e891a192cfd00d88af1af98, application version 0.56.2.
- B: Casetodian 592a15eba686ef2955cf5d3874c82df0baf8a2f4, application version 0.57.0.
- Prisma schema, migrations and pnpm lockfile are identical between A and B (git diff exit 0).
- Build each release from its pinned source; preserve immutable container image IDs and
  content hashes. Verify distinct backend artifact bytes, not only a version label.
- Services: API, MCP and worker production runtime, plus web serving built assets.
- Isolated internal backend/database network plus a separate ingress bridge for web.
  Only web publishes a loopback port. API/MCP/worker readiness is probed over HTTP
  from inside the internal network; web and its proxied anonymous API are tested via localhost.
- Use synthetic test-only service configuration; source .env is not copied into images.
- No external service calls, production deploy, schema rollback, or data restore.
  Authenticated user journeys and Keycloak deployment are outside this smoke test.

## Backup and execution

Preserve both immutable images as application recovery artifacts and hash them before
mutation. No protected pre-existing database or files exist in the dedicated experiment;
create a synthetic sentinel and verify its value after each transition. No database
backup/restore or lossless migration-recovery claim is made.

Run versions sequentially, never overlapping benchmark builds/gates/deployments.
For each version: deploy A, verify health/readiness and image identity; deploy B and
verify; roll back to A and verify. Inject a bad database endpoint into B, require
readiness failure, then recover to the pinned A image and verify the sentinel.
User's local deploy/rollback test request authorizes this bounded automatic application
recovery for the injected failure. Stop on an uncertain or failed recovery.

Before each mutation, retain an attempt record with target/recovery image IDs,
configuration reference, timestamps and expected health. Use a 60-second readiness
limit with bounded polls, and inspect actual state on failure. Preserve failure output
in ignored private logs; retained evidence contains no environment values or credentials.

Pass criteria: correct image ID and /health for all services, /ready for API/MCP,
web HTML/assets available, protected API rejects anonymous access, synthetic database
sentinel unchanged, and wrong-DB B rejected before verified A recovery. Cleanup after
all token, gate and deployment results are retained. Keep required evidence if blocked.
