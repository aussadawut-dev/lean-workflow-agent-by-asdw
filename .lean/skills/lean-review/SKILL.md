---
name: lean-review
description: Review the current change at the required depth; HIGH depth uses an independent reviewer. Use after implementation and validation, or when asked.
user-invocable: true
argument-hint: "[diff or scope]"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md`; keep model reasoning effort separate.

Scope: $ARGUMENTS (default: uncommitted changes)

1. Read `.lean/policy/REVIEW.md` and run `python3 .lean/bin/lean progress set review`.
2. Confirm deterministic validation already passed. If it has not run, run the Quality Gate commands from `.lean/PROJECT.md` first.
3. Determine depth: the deeper of risk and quality floor from the Task Contract. If there is no contract, infer risk per `.lean/policy/CONTRACTS.md`.
4. Review against the Task Contract and the project standards routed from `.lean/PROJECT.md`:
   - `LOW` — self-check against acceptance criteria.
   - `MEDIUM` — focused diff review yourself.
   - `HIGH` — use an independent reviewer: Claude's `reviewer` subagent, or a Codex or agy subagent or
     fresh session. Give it `.lean/roles/reviewer.md`, the Task Contract and diff range only, without
     your reasoning. Start a Codex reviewer fresh (`spawn_agent` with `fork_turns: "none"`), never as
     a fork of your thread. Select its size, model and effort by `.lean/policy/MODELS.md` and pass
     them on the spawn; the definition's `model: inherit` is only Claude's portable fallback. If no
     independent reviewer is available, follow `.lean/policy/REVIEW.md` and report `BLOCKED`.
5. Act on the verdict under `Rounds` in `.lean/policy/REVIEW.md`, which bounds both branches:
   - `PASS` — the review is over; anything applied after it is a new contract.
   - `REWORK` — fix the findings, re-run validation, review again with delta context only.
6. Have the HIGH reviewer record its verdict through `python3 .lean/bin/lean evidence record-review` as `REVIEW.md` specifies. Never record it yourself; if the reviewer cannot, report `BLOCKED`. Check the receipt against the shipping state and exact contract; later edits invalidate it. Report the Review Contract, scope and round.
