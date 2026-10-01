# Contributing

This repository is the Lean Workflow template itself: workflow files only, no application code.
A change here reaches every project that upgrades, so it is held to the workflow's own bar.

## Before opening a pull request

```sh
shellcheck .claude/hooks/*.sh .lean/bin/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-mode.sh
.lean/tests/test-tracker.sh
.lean/tests/test-hooks.sh
.lean/tests/test-queue.sh
.lean/tests/test-structure.sh
```

Those are the Quality Gate commands in `.lean/PROJECT.md`, and CI runs the same seven.

Then fill in the pull request template. It is the Result Contract; a workflow that asks every
change for evidence should carry its own.

## Rules for changing the workflow

- `CLAUDE.md` is canonical. Edit it first, then sync the fallback rules in `AGENTS.md`.
- A new rule needs evidence that the current behavior fails without it — a real run, not a hunch.
  The `1.4.0` entry in `.lean/CHANGELOG.md` is the pattern: five headless runs, then rules
  *removed* because they were never read.
- Prefer deleting a rule to adding one. Every line in here is loaded into someone's context.
- A behavior change in a hook needs a case in `.lean/tests/test-hooks.sh`, one in
  `.lean/scripts/check-structure.sh` a case in `.lean/tests/test-structure.sh`, and one in
  `.lean/bin/` a case in the matching `test-mode.sh`, `test-tracker.sh`, or `test-queue.sh`.
- `.lean/bin/` is workflow code that runs during a session, not a self-check. `.lean/scripts/` and
  `.lean/tests/` are the self-checks a project may delete; `bin/` is not.
- `.lean/policy/` is workflow-owned and replaced on upgrade. Project-specific rules belong in
  `.lean/PROJECT.md`, which upgrades never touch.
- Bump the version in `.lean/CHANGELOG.md` and `.lean/README.md`. The structure check fails if
  either is missing it or the two disagree. `.lean/PROJECT.md` mentions the version too, but it
  is project-owned and not checked, so keep it in step by hand.
- MAJOR also covers moving paths an existing install depends on. Such an entry needs migration
  steps, and they must say to run before the `Upgrading` steps, not after.
