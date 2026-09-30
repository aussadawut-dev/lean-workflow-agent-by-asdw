# Recovery

## Classify the failure

- **Transient execution** (network, flaky tool, timeout) -> retry unchanged, bounded.
- **Implementation failure** (tests/validation fail) -> rework the implementation.
- **Review failure** (`REWORK` verdict) -> rework against the findings. Rounds are capped; see `REVIEW.md`.
- **Pre-existing or out-of-scope failure** (fails without your change, or in code the task does not cover) -> do not fix it; report `BLOCKED` and ask, even when a gate is blocking you.
- **Blocked** (missing access, ambiguity, contradictory requirements) -> stop and report; do not guess.

## Rules

- Use delta context on retry and rework.
- Change approach after repeated identical failures; do not loop.
- Escalate model/effort only per `MODELS.md`.
- Never weaken tests, checks, or the quality floor to get past a failure.
- If the floor cannot be met, report `BLOCKED` or `FAILED` with evidence.
