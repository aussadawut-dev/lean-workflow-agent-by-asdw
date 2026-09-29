# Testing

- Tests must be **meaningful**: they fail when the behavior is wrong.
- Testing is **risk-based**: depth follows risk, not line counts.
- Test only what is **applicable**: docs and pure config changes may need none; state that explicitly.
- **Bug fixes require a regression test** that fails before the fix and passes after.
- Behavior changes require tests covering the changed behavior and its edges.
- Prefer the repository's existing test tooling and conventions (see `PROJECT.md`).
- If no test tooling exists, say so in the Result Contract; add minimal tooling only when the task requires it.
- Do not weaken or delete a test to make it pass.
