# Testing

- Tests must be **meaningful**: they fail when the behavior is wrong.
- Testing is **risk-based**: depth follows risk, not line counts.
- Test only what is **applicable**: docs and pure config changes may need none; state that explicitly.
- **Bug fixes require a regression test** that fails before the fix and passes after.
- Behavior changes require tests covering the changed behavior and its edges.
- Prefer the repository's existing test tooling and conventions (see `.lean/PROJECT.md`).
- If no test tooling exists, say so in the Result Contract; add minimal tooling only when the task requires it.
- Do not weaken or delete a test to make it pass.

## Run only what the change can affect

While working, run the tests the change can affect and nothing more; run the full suite at release and in CI. Projects record their own selection command in `.lean/PROJECT.md`. Lean's own workflow tests use:

- Categories: `.lean/tests/unit/` (in-process logic), `.lean/tests/hooks/` (guard, gate and hooks in disposable repositories), `.lean/tests/e2e/` (whole command flows such as updates and spawning).
- Impact map: `.lean/tests/impact.json` maps changed paths to test files or categories. Only paths in its workflow `scope` can affect these tests, so a project's application changes never run them; documentation and project-settings globs map to lint only.
- `lean test --changed` selects from the working tree, the index, untracked files and commits no remote has yet. A documentation-only change runs lint only; a changed path no rule covers runs everything, so selection never silently skips. `--list` shows the selection without running it; `--tier unit` or named files run a part; `--all` runs everything. `--smoke` runs the short `smoke` list in impact.json: what a project that uses Lean runs of Lean's own tests in its gate, since every Lean update changes Lean's code and `--changed` would then run the whole suite.
- A new test file must be reachable from the impact map, or it only runs in full runs.
