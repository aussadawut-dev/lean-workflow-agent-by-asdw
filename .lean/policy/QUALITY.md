# Quality

## Quality floor

| Level | Meaning |
|---|---|
| `STANDARD` | Correct, tested where behavior changes, validated. |
| `HIGH` | STANDARD plus risk review and edge-case coverage. |
| `VERY_HIGH` | HIGH plus independent review and explicit failure-mode analysis. |

## Budget

`CHEAP | BALANCED | EXPENSIVE` controls effort and cost, never the floor. If the floor cannot be met within budget, report it; do not silently downgrade.

## Quality Gate

DONE requires all of:

1. Task Contract acceptance checks satisfied with evidence.
2. Deterministic validation passed (or not-applicable stated).
3. Tests present for behavior changes.
4. Review completed at the required depth (deeper of risk and quality; see `REVIEW.md`).
5. No unreported skipped checks.

For Claude, the `Stop` hook enforces step 2 when Quality Gate commands are defined in `.lean/PROJECT.md`.

**No evidence, no DONE.**
**No useful evidence, no extra tokens.**
