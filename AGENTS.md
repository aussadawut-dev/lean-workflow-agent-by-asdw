# Agent Instructions

This repository uses Lean Workflow Baseline #1. The canonical contract is `CLAUDE.md`.

**Before any task, read `CLAUDE.md` and `.lean/README.md`. Do not start work without them.**

The project's workflow mode is the value in the mode block of `.lean/PROJECT.md`. Follow it; if it
is unset, ask the user for it once and record it with `.lean/bin/mode.sh set <mode>`. What each mode
adds: `.lean/policy/MODES.md`.

If you cannot read them, these rules still apply:

- Do not declare DONE without evidence.
- Behavior changes require meaningful tests; bug fixes require a regression test.
- Never silently downgrade the requested quality floor.

<!-- The three rules above are a fallback copy. Edit CLAUDE.md first. -->
