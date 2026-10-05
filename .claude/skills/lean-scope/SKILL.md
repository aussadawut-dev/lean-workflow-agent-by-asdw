---
name: lean-scope
description: Draft a clear spec for non-trivial work, get user approval before implementation, and stop for approval when proposed changes leave the agreed scope.
user-invocable: false
---

# Lean Scope

Use for non-trivial implementation work or when explicitly invoked. Skip a formal spec for trivial, mechanical edits unless the user asks. Read-only inspection and drafting the proposed scope are allowed before approval; do not change product code, configuration, or other implementation files until the user approves the spec. An explicit request to implement does not by itself approve a new spec created by this skill.

## Draft the scope

Read the relevant `AGENTS.md`, project context, and current tracker. Reuse a user-approved scope already recorded for this work; do not ask the user to approve it again. Draft a new scope or a material amendment only when no matching approved scope exists. Use existing accepted decisions rather than reopening them. If choosing an approach needs evidence, use `lean-research`; if a material decision remains open, use `lean-grill` before dependent implementation.

Write a concise draft with:

- Goal and intended user-visible outcome.
- In-scope behavior and explicit non-goals or out-of-scope work.
- Observable acceptance criteria and relevant validation.
- Constraints, dependencies, assumptions, and material open questions.
- Likely affected components or files when repository evidence makes them clear; label uncertain locations as estimates.

Show the draft to the user and ask for approval or corrections. Then pause. Do not treat silence, elapsed time, or approval of a different decision as scope approval. If the user requested analysis or a spec only, return the draft without implementing it.

## Protect the approved scope

After approval, record the accepted scope in the owning tracker before implementation when tracker mode requires it. Keep a simple scope ledger against the approved goal and acceptance criteria as work proceeds.

Before a proposed change, check whether it is needed for an accepted criterion and remains within the agreed behavior and constraints. Continue with routine implementation choices that fit the scope; do not interrupt for every small detail. If a necessary change would add behavior, alter acceptance, expand affected areas materially, or change a recorded decision, stop that dependent work and ask the user first. State the proposed delta, why it is needed, its impact on effort or risk, and a recommended option. Independent work that remains within scope may continue.

When the user approves a scope change, update the owning tracker before continuing with the affected work. At completion, map each acceptance criterion to evidence and name any deferred work without silently absorbing it.

This skill defines and guards scope. `lean-research` supplies evidence, `lean-grill` resolves material decisions, `lean-task` runs the implementation workflow, and `lean-review` reviews the result. Scope approval does not authorize publication, deployment, or unrelated external writes.

$ARGUMENTS
