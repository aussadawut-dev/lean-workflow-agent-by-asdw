---
name: lean-task
description: Run a task through contract, accepted scope, configured execution, tests, validation, review and Quality Gate.
user-invocable: true
argument-hint: "<task description>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

Task: $ARGUMENTS

1. Write the contract from `AGENTS.md` before changes. Infer risk/quality; read `.lean/policy/CONTRACTS.md` when needed.
2. Read `.lean/PROJECT.md` and use `python3 .lean/scripts/workflow.py show`. Follow `.lean/policy/WORKFLOW.md`. Standard uses session records; non-trivial tracker/full work uses one owning tracker. Trivial tasks need no new tracker. Full tasks require appropriate items/claims before scope edits, including trivial edits inside existing claims.
3. Use `/lean-scope` for non-trivial work: reuse already accepted scope; draft and get approval only when no matching scope exists or a material expansion is proposed. Use `/lean-research` for evidence-backed alternatives and `/lean-grill` for unresolved material decisions/high-risk boundaries. Clear accepted work need not reopen decisions.
4. Follow configured execution: direct work stays with the active agent; delegated work uses the Controller/worker procedure in `.lean/skills/lean-multi-agent/SKILL.md`. Select models/effort under `.lean/policy/MODELS.md` and record any dispatch. Consult a project catalog only alongside current runtime options under MODELS; use `/lean-model-update` when refresh is requested, never automatically apply it or switch the session. Concurrent workers require explicit user intent and exclusive independent scopes. Preserve the required review depth when delegation is unavailable.
5. Work, then test. Behavior changes need meaningful tests; bug fixes demonstrate regression fails before the fix and passes after. Validate deterministically with the Quality Gate in PROJECT.
6. Review at the deeper of risk and quality. HIGH depth requires an independent reviewer: Claude's `reviewer` subagent, or a Codex subagent/fresh session. Give it contract and diff without author reasoning; select model/effort under `.lean/policy/MODELS.md`. Report BLOCKED if independent review cannot run. Follow bounded rounds in `.lean/policy/REVIEW.md`.
7. Verify claim completion/evidence when applicable and synchronize tracker/session records. Run `/lean-gate` and report the Result Contract, including validation/review evidence and unverified work. Worker completion alone does not mark the task DONE.
