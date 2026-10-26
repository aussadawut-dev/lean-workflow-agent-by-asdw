---
name: lean-task
description: Run a task through contract, scope, execution, tests, validation, review and Quality Gate, showing progress at each phase.
user-invocable: true
argument-hint: "<task description>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md`; keep model reasoning effort separate.

Task: $ARGUMENTS

Run `python3 .lean/bin/lean progress set <phase>` on entering each phase below and show the bar it prints (`.lean/policy/WORKFLOW.md`).

1. **contract** — write the contract from `AGENTS.md` before changes. Infer risk/quality; read `.lean/policy/CONTRACTS.md` when needed. Set `--task '<short title>'` with the first progress call.
2. **scope** — read `.lean/PROJECT.md` and `lean mode show`; select context under `.lean/policy/CONTEXT.md`. Standard uses session records; non-trivial tracker/full work uses one owning tracker (`lean tracker new`). Full tasks need items/claims before scope edits. Use `/lean-scope` for non-trivial work: reuse accepted scope and treat a clear implementation request as approval of the matching scope; wait only when the request is ambiguous, a material decision is open, risk is HIGH, or a material expansion is proposed. Use `/lean-research` for evidence-backed alternatives and `/lean-grill` for unresolved material decisions or high-risk boundaries.
3. **implement** — follow configured execution. Direct work stays here and spawns only as `.lean/policy/MODELS.md` allows (one sized agent at a time by default; more only through `/lean-agents`). Delegated work uses the Controller/worker procedure in `.lean/skills/lean-agents/SKILL.md`. Record every dispatch. Report counts with `--done/--total` when the work splits into parts.
4. **test** — behavior changes need meaningful tests; bug fixes show the regression test failing before the fix and passing after. While iterating, run only what the change can affect (`.lean/policy/TESTING.md`).
5. **validate** — run the deterministic checks from PROJECT.
6. **review** — synchronize tracker/session progress first, so review covers it. Review at the deeper of risk and quality. HIGH depth requires an independent reviewer: Claude's `reviewer` subagent, or a Codex/agy subagent or fresh session, given contract and diff without author reasoning, with model/effort sized under `.lean/policy/MODELS.md`. Report BLOCKED if independent review cannot run. Follow the bounded rounds in `.lean/policy/REVIEW.md`.
7. **gate** — verify claim completion and evidence when applicable and record the review result and status in the tracker/session records (tracker edits under `docs/tracking/` keep the receipt valid). Run `/lean-gate`, then `lean progress set done`, and report the Result Contract with the final bar, validation/review evidence and unverified work. Worker completion alone does not mark the task DONE.
