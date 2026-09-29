# Contracts

## Task Contract

- **Goal** — what must be true when finished.
- **Scope** — files/areas in and out.
- **Quality** — `STANDARD | HIGH | VERY_HIGH`.
- **Budget** — `CHEAP | BALANCED | EXPENSIVE`.
- **Risk** — `LOW | MEDIUM | HIGH`.
- **Acceptance** — observable checks that prove completion.

Quality and budget are independent. Budget never lowers quality.

## Defaults

Do not ask the user for these values. Use the defaults, infer risk, and state the result in one line. The user may override any value at any time.

- **Quality** — `STANDARD`, unless the user asks for more or risk is `HIGH` (then at least `HIGH`).
- **Budget** — `BALANCED`.
- **Risk** — inferred:
  - `HIGH` — auth, permissions, payments, secrets, data deletion or migration, security boundaries, public API contracts, anything hard to reverse. Also any area listed under High-risk areas in `PROJECT.md`.
  - `MEDIUM` — behavior changes in shared code, multi-file refactors, dependency changes, configuration that affects runtime.
  - `LOW` — docs, comments, tests only, isolated local changes.
- When unsure between two levels, choose the higher one.

## Result Contract

Scale the report to the task. A trivial task needs one line.

- **Status** — `DONE | BLOCKED | FAILED`.
- **Changes** — what changed and where.
- **Evidence** — commands run and their outcomes, tests added/run.
- **Not verified** — anything skipped, with reason.
- **Follow-ups** — remaining work, if any.

## Review Contract

- **Verdict** — `PASS | REWORK`.
- **Findings** — location, problem, severity, suggested fix.
- **Scope** — what was and was not reviewed.
