# Context tokens: Lean 4.17.0 vs 5.0.0

Static token inventories of the workflow files an agent reads, measured with the same method as `docs/benchmarks/2026-10-25`. Raw data: `context-tokens.json`. Reproduce: `python3 docs/benchmarks/2026-10-26/measure_context.py > context-tokens.json`.

## Method

- Per-file text tokens summed with tiktoken 0.12.0 (`o200k_base`, `cl100k_base`). tiktoken is a local measurement tool, not a Lean dependency.
- 4.17.0 files come from tag `v4.17.0` (9b6252d); 5.0.0 files from the working tree of `feat/refactor-v4` (HEAD c5687c8, with uncommitted edits to tracked files at measurement time).
- Startup inventory: `AGENTS.md` and `.lean/README.md` (loaded through the `CLAUDE.md` imports). The retained 4.17 method counted nothing else at startup, so SessionStart hook output is not counted for either version.
- Fixed-task inventory: the 11 files the 4.17 method listed (startup pair, four skills, five policies).
- Gate source inventory: the five gate/guard files the 4.17 method listed, mapped by role to v5 modules.
- Workflow-owned files: tracked non-symlink files under `.lean/`, `.claude/`, `.codex/`, `.agents/` plus `AGENTS.md`, `CLAUDE.md`, excluding project-owned `PROJECT.md`, `config.json`, `skill-effort.json`.

## Reproduction check of the 4.17 numbers

Run on `v4.17.0` files, `o200k_base`: startup 2,213 and fixed-task 11,146, equal to the retained 2026-10-25 values. Gate source 28,732 equals the retained "after" value; `cl100k_base` also matches (2,211 / 11,153). Same file lists, so the numbers are comparable.

## File mapping

Startup and fixed-task files have the same path in both versions (listing below). Mapping is by role, not a line-for-line port.

| 4.17 path | 5.0 path | 4.17 tokens | 5.0 tokens |
|---|---|---:|---:|
| `AGENTS.md` | `AGENTS.md` | 1,504 | 1,706 |
| `.lean/README.md` | `.lean/README.md` | 709 | 690 |
| `.lean/skills/lean-task/SKILL.md` | `.lean/skills/lean-task/SKILL.md` | 685 | 669 |
| `.lean/skills/lean-scope/SKILL.md` | `.lean/skills/lean-scope/SKILL.md` | 1,335 | 913 |
| `.lean/skills/lean-review/SKILL.md` | `.lean/skills/lean-review/SKILL.md` | 617 | 576 |
| `.lean/skills/lean-gate/SKILL.md` | `.lean/skills/lean-gate/SKILL.md` | 578 | 433 |
| `.lean/policy/CONTEXT.md` | `.lean/policy/CONTEXT.md` | 823 | 600 |
| `.lean/policy/CONTRACTS.md` | `.lean/policy/CONTRACTS.md` | 1,390 | 1,408 |
| `.lean/policy/TESTING.md` | `.lean/policy/TESTING.md` | 146 | 400 |
| `.lean/policy/REVIEW.md` | `.lean/policy/REVIEW.md` | 1,017 | 877 |
| `.lean/policy/QUALITY.md` | `.lean/policy/QUALITY.md` | 2,342 | 1,877 |

Gate source (`o200k_base`):

| 4.17 path | 5.0 path | 4.17 tokens | 5.0 tokens |
|---|---|---:|---:|
| `.codex/hooks/quality_gate.py` | `.lean/lean/hooks.py` | 1,971 | 2,990 |
| `.lean/scripts/contract_guard.py` | `.lean/lean/guard.py` | 11,175 | 11,243 |
| `.lean/scripts/gate_evidence.py` | `.lean/lean/evidence.py` | 7,371 | 7,566 |
| `.lean/scripts/quality-gate.sh` | `.lean/lean/gate.py` | 4,238 | 6,107 |
| `.lean/scripts/submodule.py` | `.lean/lean/target.py` | 3,977 | 3,932 |

Unmapped: v5 has other `.lean/lean/*.py` modules (cli, records, update, spawn, ...) with no counterpart in the 4.17 gate list; they appear only in the supplementary "all executable source" row. `.lean/skills/lean-playbook` (the 4.17 deployment-optional set) is not in either fixed set and does not exist as a v5 skill. 4.17 also had `.claude/hooks/*` and 17 `.lean/scripts` files, counted only in the supplementary row.

## Results

| Inventory | Encoding | 4.17.0 | 5.0.0 | Delta | % |
|---|---|---:|---:|---:|---:|
| Startup (AGENTS.md + .lean/README.md) | o200k_base | 2,213 | 2,396 | +183 | +8.3% |
| Startup (AGENTS.md + .lean/README.md) | cl100k_base | 2,211 | 2,392 | +181 | +8.2% |
| Fixed-task read set (11 files) | o200k_base | 11,146 | 10,149 | -997 | -8.9% |
| Fixed-task read set (11 files) | cl100k_base | 11,153 | 10,154 | -999 | -9.0% |
| Gate source inventory (5 files) | o200k_base | 28,732 | 31,838 | +3,106 | +10.8% |
| Gate source inventory (5 files) | cl100k_base | 28,516 | 31,567 | +3,051 | +10.7% |
| All executable source (supplementary) | o200k_base | 70,637 | 67,164 | -3,473 | -4.9% |
| All executable source (supplementary) | cl100k_base | 70,014 | 66,650 | -3,364 | -4.8% |
| Skill frontmatter, all skills (supplementary) | o200k_base | 1,025 | 644 | -381 | -37.2% |
| Skill frontmatter, all skills (supplementary) | cl100k_base | 1,021 | 644 | -377 | -36.9% |

Workflow-owned size: 4.17.0 97 files / 18,119 lines (74 / 9,086 excluding tests); 5.0.0 83 files / 15,289 lines (56 / 8,082 excluding tests).

Reading: startup grew (AGENTS.md +202 tokens, README -19); the fixed-task set shrank because scope, gate, review and quality docs shortened, partly offset by TESTING.md and the review-pending rule added to QUALITY.md; gate source grew because the Python gate/hook modules are larger than the shell/adapter they replace, while total executable source and skill metadata shrank.

## Limits

- Static inventories only. They exclude runtime prompts, tool traffic, model output, retries and caching.
- Fixed sets are comparable input inventories, not required reads for every task; focused range reads can cost less.
- The v5 side was measured from a working tree with uncommitted changes to tracked files (for example `.lean/lean/spawn.py`); re-run after committing for a pinned figure.
- Supplementary rows were not part of the 4.17 retained method. Skill frontmatter counts 18 v4 skills (including the optional pack) against 11 v5 skills.
- These numbers do not prove usage, cost or speed savings.
