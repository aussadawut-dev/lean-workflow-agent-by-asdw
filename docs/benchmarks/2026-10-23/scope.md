# Lean 4.7.0 versus current dirty: Casetodian experiment

Requested: token usage comparison, Quality Gate timing, local deployment and rollback.
Use the same Casetodian develop commit for both workflow versions. Preserve current dirty
workflow bytes before benchmarking. Record exact revisions, commands, status and timings.
Do not treat input-context token counts as actual model usage. User selected workflow/context token counting only; no model sessions will run.
Measure one full gate per version and repeated synthetic wrapper/cache checks separately. Report dependency warm-up and shared-host limitations; a single full run is exploratory evidence.
Deploy and roll back application artifacts on loopback only, with an isolated local database.
Database schema rollback is not included; no source database or existing service is modified.
The user supplied the source .env; secret values stay ignored and are never included in evidence.
After all results are retained, remove the experimental submodule and experiment resources.
Keep it while required results remain incomplete; do not remove the original checkout.
