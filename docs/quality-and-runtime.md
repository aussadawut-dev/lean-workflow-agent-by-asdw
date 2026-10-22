# Quality, review and runtime integration

[Back to README](../README.md)

Run the CLI examples from the repository root.

## One shared contract

[AGENTS.md](../AGENTS.md) holds the shared rules. [CLAUDE.md](../CLAUDE.md) imports it. Both runtimes discover nine core skills through symlinks, with eight more available through the optional pack.

The active agent owns the task unless the project records a different Controller. It needs evidence before reporting DONE, must keep the quality level you requested, and should spend extra effort only when it has a useful reason. Project additions have their own sections so upgrades can preserve them.

## Before changing files

The agent writes a one-line Task Contract with risk, quality and observable acceptance. It uses accepted decisions, researches alternatives when useful, and resolves important open decisions before work that depends on them. Routine work inside accepted scope can continue without asking again.

It starts with enough context for the task and follows the policy router when it needs more. `.lean/PROJECT.md` holds actual repository facts and commands.

## Tests and review

Behavior changes need meaningful tests. A bug fix needs a regression test shown failing before the fix and passing afterward. Deterministic validation runs before semantic review.

Review depth is the deeper of risk and the requested quality floor. HIGH-depth review uses an independent reviewer who receives the Task Contract and final diff without the author's reasoning.

Review rounds are bounded. After a second REWORK, one final repair/review pass must resolve the findings or report BLOCKED. PASS ends that cycle; edits made afterward need a new contract.

## Quality Gates and completion

Your gate commands live in [.lean/PROJECT.md](../.lean/PROJECT.md). Both providers use the shared auto/manual policy. In auto mode, Claude Stop and a trusted, activated Codex Stop adapter run the checks. Direct calls to the shared runner always execute:

```sh
bash .lean/scripts/quality-gate.sh --root .
```

Checks rerun by default, including continued Stops after failure. A missing or empty gate blocks completion with setup guidance. SessionStart records a change baseline; it does not validate the project.

`--cache-tree` is an opt-in cache for checks whose inputs are entirely visible to Git. This repository uses it for Claude Stop. Unchanged state can reuse a PASS while contract and required review checks still run. Changed files or a previous refusal trigger fresh validation.

Changes to tools, environment or ignored dependencies need a fresh direct run. Downstream projects whose checks depend on those inputs should remove `--cache-tree` from their Stop command. For HIGH-depth work, include `--require-review --contract '<exact contract line>'` when validating and checking the receipt together.

The Claude adapter checks contract provenance when transcript metadata is available. HIGH-review receipts bind the reported review to the contract and current shipping state. Local hashes detect gate-control changes until matching prior user approval is recorded or an independent HIGH-depth PASS review covers them. Controls that equal a trusted upstream ref listed in PROJECT.md (`<!-- trusted-control-refs: ... -->`), for example after merging a reviewed release branch, are accepted automatically; local edits still need approval or an independent HIGH-depth PASS review that covers them. See [.lean/policy/QUALITY.md](../.lean/policy/QUALITY.md) for exact commands and limits.

These checks catch stale evidence and mistakes, but remain writable by an agent with repository access. Contract truth, regression timing, reviewer identity and record evidence still depend on following the procedure. Projects needing enforcement outside the agent should use trusted CI and protected merge permissions.

All shared gate entry points hold a lock for that checkout while checks run. A busy or unavailable lock reports NOT_RUN. Retry after the owning processes exit; never delete a live lock file. Direct commands outside the runner are not serialized. The lock does not freeze edits or prove checks passed.

Pre-existing or out-of-scope failures, missing tools, and unavailable required reviewers/workers stay BLOCKED with evidence. Workflow self-tests alone cannot establish application correctness.

## Auto and manual mode

Inspect the setting with `python3 .lean/scripts/gate_mode.py`. Add `auto` or `manual` to save an explicit choice. See [.lean/policy/QUALITY.md](../.lean/policy/QUALITY.md) for gate automation rules.

Workspace-owned `.codex/quality-gate.json` stores the preference. Missing settings mean auto. Preferences survive upgrades and are excluded from releases. Both providers read the setting, including for a selected submodule target.

Manual mode skips automatic full checks and reports NOT_RUN. Focused checks can continue. A full run at completion needs applicable user authorization, reusing matching workset/batch approval. Until validation and review cover the final work, keep VALIDATING/BLOCKED.

Explicit entry points include the shared runner, `python3 .codex/hooks/quality_gate.py run`, and `CLAUDE_GATE_FORCE=1 .claude/hooks/quality-gate.sh`. For HIGH work, supply the exact `--contract` and `--require-review`. Automatic Codex Stops can reuse only a receipt verified against the current state; they cannot establish acceptance or contract provenance for a new task.

Changing the mode is a protected control change. Inspect the full controls delta and record only already matching approval through the existing accept-controls procedure. The mode command cannot approve unrelated edits. Invalid policy blocks the provider adapters. Manual mode and released Stops still require the same completion evidence and review.

## Runtime integration and limits

Claude's `.claude/settings.json` supplies SessionStart/Stop hooks, read-only Git permissions and `.env` read denies. These settings apply to Claude. Keep secrets out of trackers, queue items and dispatch messages; local settings are not a general secret-protection guarantee. Headless Claude also needs its runtime's workspace trust and tool permissions.

Codex definitions live in `.codex/hooks.json`. Activation and trust belong to the runtime and need separate verification. Until verified, follow AGENTS and run checks explicitly. Installing adapter files or passing adapter tests does not prove the hooks are active in your Desktop session. Other agents can follow the contract, but native adapters are supplied only for Claude and Codex.

Workflow self-tests run locally and in GitHub Actions on Ubuntu with Python 3.9. They cover onboarding, modes, lease ownership, dependencies/evidence, downgrade guards, dry-run preservation, worker races, upgrade-back validation, canonical routing and discovery links. Smoke tests isolate reusable assets and preserve the host project's license and records. Add your application's own checks alongside them.
