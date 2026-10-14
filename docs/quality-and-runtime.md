# Quality, review and runtime integration

[Back to README](../README.md)

Run CLI examples from the repository root.

## One shared contract across agents

[AGENTS.md](../AGENTS.md) is canonical. [CLAUDE.md](../CLAUDE.md) imports it, and both runtimes discover nine core procedures through symlinks. Ten optional procedures are available through the optional discovery pack. No provider is the required primary agent; the active agent owns the task unless the project records a different Controller.

The contract requires acceptance evidence before reporting DONE, preserves an explicitly requested quality floor, and limits extra effort to work with a useful reason. Project-specific additions have dedicated sections so upgrades can preserve them.

## Planning, scope and decisions

A one-line Task Contract identifies risk, quality and observable acceptance before changes begin. The workflow supports reusing accepted scope, gathering evidence for alternatives and resolving material decisions before dependent implementation. Routine work within accepted scope needs no repeated approval.

Agents start with the smallest sufficient context. The policy router points them to deeper rules only when needed, and `.lean/PROJECT.md` supplies actual repository facts rather than an imposed stack or architecture.

## Meaningful tests and risk-based review

Behavior changes require meaningful tests. Bug fixes require a regression test demonstrated failing before the fix and passing afterward. Deterministic validation runs before semantic review.

Review depth follows the deeper of task risk and quality floor. HIGH-depth review requires an independent reviewer receiving the Task Contract and shipping diff without the author's reasoning. The review loop is bounded: after a second REWORK, one final pass must resolve the findings or report BLOCKED. A PASS ends that review cycle.

## Quality Gates and honest completion

Project-owned gate commands live in [.lean/PROJECT.md](../.lean/PROJECT.md). Both providers follow shared auto/manual gate policy. Claude Stop and an activated Codex Stop adapter run shared checks in auto mode; explicit runner calls always execute.

Checks rerun by default, including on continued Stops after failure. Missing or empty gates block with an onboarding message. SessionStart records only a change baseline. `--cache-tree` is an explicit choice for checks whose inputs are entirely Git-visible; it does not cover environment or ignored dependencies.

This repository opts its Claude Stop hook into `--cache-tree`: an unchanged state reuses a passing run while contract and required review checks still run. Changed files or a previous refusal trigger fresh validation. After changing tools, environment or ignored dependencies, force a fresh run with `bash .lean/scripts/quality-gate.sh --root .` (include `--require-review --contract '<exact contract line>'` for HIGH work). Downstream projects should remove the Stop command's `--cache-tree` option when their checks depend on inputs outside Git-visible state.

The Claude adapter checks assistant contract provenance when transcript metadata is available. HIGH review receipts bind the reported review to the current contract and shipping state. Local hashes also catch changes to hooks/settings/gate commands until an already user-approved change is recorded. These mechanisms detect mistakes and stale evidence; an agent with write access can still alter them. Contract truth, regression timing, reviewer identity and task-record evidence remain procedural. Codex also has a lifecycle adapter; activation and trust must be verified separately. See [.lean/policy/QUALITY.md](../.lean/policy/QUALITY.md) for exact limits and commands.

All shared gate entry points hold a per-checkout lock for the lifetime of their checks. A busy or unavailable lock reports NOT_RUN; retry after the owning processes exit and never delete a live lock file. Direct validation commands outside the shared runner are not serialized. The lock does not freeze source edits or establish passing evidence.

Projects requiring enforcement outside the agent must use trusted CI and protected merge permissions. Local self-tests do not prove application correctness. Pre-existing/out-of-scope failures or unavailable required reviewers/workers remain BLOCKED with evidence.

## Auto and manual gate mode

Inspect with `python3 .lean/scripts/gate_mode.py`; explicitly save `auto` or `manual` as its final argument. The optional `lean-quality-gate-mode` skill wraps the same CLI. Missing workspace `.codex/quality-gate.json` means auto; the project preference is preserved on upgrades and is excluded from releases. Both Claude and Codex read it, including when a submodule target is selected.

Manual mode skips automatic full checks and reports NOT_RUN. Focused validation continues; a full run requires applicable user authorization, reusing matching workset/batch approval. Deferral leaves VALIDATING/BLOCKED. An explicit direct runner call, `python3 .codex/hooks/quality_gate.py run`, or `CLAUDE_GATE_FORCE=1 .claude/hooks/quality-gate.sh` runs the checks. For HIGH work pass the exact `--contract` and `--require-review`; Codex automatic Stops can reuse only a receipt verified against the current shipping state; they cannot establish acceptance or contract provenance for a new task. Neither manual mode nor a released Stop waives required evidence or review.

A mode change is a protected control change. Inspect the controls delta and record only already matching approval using the existing accept-controls procedure; the mode CLI never blesses unrelated edits. Invalid policy blocks provider adapters rather than silently running or treating skipped checks as passed.

Codex definitions live in `.codex/hooks.json`. Project hooks require project-layer trust and review/trust of the exact hook definitions; changing a hook requires renewed runtime review. Use `/hooks` in the CLI and reload/start a session as applicable. This repository does not set global trust or bypass it. Until activation is verified, agents follow AGENTS and run checks explicitly. See [official OpenAI hook documentation](https://learn.chatgpt.com/docs/hooks). Adapter tests execute registered commands in temporary checkouts; they do not prove activation in the user's Desktop session.

## Runtime integration and limits

Claude's `.claude/settings.json` supplies SessionStart and Stop hooks, read-only Git permissions and `.env` read denies. These settings are Claude-specific; they do not configure Codex hooks or permissions and are not a general secret-protection guarantee. Keep secrets out of trackers, queue items and dispatch messages.

For headless Claude, follow your runtime's workspace trust and tool permission requirements. Other agents can follow the shared contract, but this repository does not provide native adapters for every runtime.

Workflow self-tests run locally and in GitHub Actions on Ubuntu with Python 3.9. They cover onboarding, modes, lease ownership, evidence/dependencies, downgrade guards, dry-run preservation, worker races, upgrade-back validation, canonical routing and discovery-link integrity. Smoke tests isolate reusable assets and preserve a configured host's project license and records. CI validates the workflow; add your application's own checks separately.
