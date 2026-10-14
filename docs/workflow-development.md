# Workflow development reference

[Back to README](../README.md)

This page covers the tools and tests inside Lean. Start with [.lean/PROJECT.md](../.lean/PROJECT.md) for project facts and the authoritative gate commands. Downstream applications keep their own structure and checks.

## Architecture

Lean uses Bash, Python 3.9+ standard-library tools, JSON and Markdown. It has no application dependencies, package manager or build step.

| Piece | What it does |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Shared contract and Claude import. The active agent owns the task unless project rules say otherwise. |
| `.lean/policy/` | Portable workflow rules, updated together with the workflow. |
| `.lean/PROJECT.md` / `config.json` | Project-owned facts, gate, mode and execution settings. |
| `.lean/scripts/quality-gate.sh` | Runs PROJECT checks directly for Codex and through provider adapters. Direct calls always run. |
| `.lean/scripts/gate_evidence.py` | Binds review receipts to shipping state and records already approved control changes. |
| `.lean/scripts/gate_lock.py` | Keeps shared gate runs separate within one checkout; busy gates report NOT_RUN. |
| `.lean/scripts/skill_effort.py` | Saves optional procedure preferences and routes active targets to their record roots. |
| `.lean/scripts/skill_pack.py` | Exposes nine core skills by default and ten optional skills when enabled. |
| `.lean/scripts/submodule.py` | Adds/reuses remote application submodules under `targets/` and separates code from target records. |
| `.lean/scripts/clean_repo.py` | Inventories files and applies exact cleanup plans with external snapshots and journaled recovery. |
| `.lean/scripts/takeover.py` | Inventories a separate target and binds approved edits to read coverage and source fingerprints. |
| `.claude/` | Claude settings, hooks, discovery links and shared reviewer entrypoint. |
| `.codex/` | Codex lifecycle definitions/adapters, requiring runtime activation and trust. |
| `.agents/skills/` | Codex discovery links to canonical skills. |
| `.github/` | Workflow self-checks in CI and the PR Result Contract template. |

The template ships unconfigured standard/direct and no task records. Preference files are created only when saved. Submodule selection is local/ignored; application gates run inside the target while workflow/catalog tools use its record root.

The cleanup and takeover helpers handle exact operations and recovery. Their shared skills handle semantic decisions and approval. Local receipts, hashes and reviewer identities detect drift and record claims; they do not establish independent authority.

## Environment

Use Bash, Git, Python 3.9+ and ShellCheck on macOS, Linux or WSL. Lease locking uses Unix `fcntl`; native Windows is unsupported.

Install ShellCheck through your environment's package manager, for example `brew install shellcheck` on macOS. If a required tool is missing, the gate reports the environment problem and completion remains blocked until validation can run.

## Test coverage

`.lean/tests/test-hooks.sh` runs Quality Gate and SessionStart tests in temporary repositories. It covers opt-in caches, baseline seeding, continued refusals, contract provenance and command failure classification. A missing command is an environment problem; an available command that fails remains a command failure, including a wrapper returning another program's 127.

Run the full Python suite with:

```sh
python3 -m unittest discover -s .lean/tests -p 'test_*.py'
```

It covers modes, claims, canonical routing and discovery links. `test_e2e.py` walks standard → tracker → full → standard, including completion, cleanup and downgrade guards. `test_guards.py` checks checklist variants, single-line tracker text and whitespace-padded agent IDs. `python3 .lean/scripts/workflow.py check` validates the current mode.

`test_takeover.py` checks read-only inventory, read attestations, source/target/approval drift, dirty/untracked preservation, claim/path boundaries, interrupted apply/rollback and snapshot integrity. Foreign-record cases cover decision-bound mappings, original/evidence preservation, blocked/cancelled states, trusted staged validation and interrupted conversion recovery.

APPLIED means writes finished. Semantic completion still needs acceptance, validation and required review. Tests use disposable repositories so the template stays clean.

## Context selection evaluation

When changing context selection, use the [routing scenarios](../.lean/skills/lean-task/references/context-scenarios.md). Record actual reads separately from expected results. Static instruction tests cannot measure agent behavior, application correctness or token savings.
