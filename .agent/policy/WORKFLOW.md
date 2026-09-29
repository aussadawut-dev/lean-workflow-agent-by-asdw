# Workflow

```
Task Contract -> Context -> Work -> Test -> Validate -> Review -> Quality Gate -> DONE
```

## Steps

1. **Task Contract** — one contract line before any change. See `CONTRACTS.md`. Trivial tasks write `Contract: trivial (<reason>)`.
2. **Context** — load the smallest sufficient context. See `CONTEXT.md`.
3. **Work** — implement using the simplest valid path.
4. **Test** — add/run tests for behavior changes. See `TESTING.md`.
5. **Validate** — deterministic checks first (build, lint, typecheck, tests). Commands live in `.agent/PROJECT.md`.
6. **Review** — depth by risk. See `REVIEW.md`.
7. **Quality Gate** — verify evidence against the quality floor. See `QUALITY.md`.

## Trivial task

A task is trivial when all hold:

- Risk is `LOW`.
- No behavior change, or a change fully covered by an existing test that is run.
- One file, or a mechanical edit across a few files (rename, typo, formatting).
- The goal is unambiguous.

Trivial tasks use the one-word contract and skip formal review. They still need evidence before DONE, such as a passing check or a stated reason none applies.

## Execution modes

- `DIRECT` — default.
- `SEQUENCE` — only for real dependencies between steps.
- `PARALLEL` — only for genuinely independent work.

## States

`PLANNED -> IN_PROGRESS -> VALIDATING -> REVIEWING -> DONE`
Failure states: `BLOCKED`, `FAILED`. See `RECOVERY.md`.

DONE is set only by the Quality Gate, never by the worker's own claim.
