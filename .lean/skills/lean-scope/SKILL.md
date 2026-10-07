---
name: lean-scope
description: Draft a clear spec for non-trivial work, get user approval before implementation, and stop for approval when proposed changes leave the agreed scope.
user-invocable: false
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

# Lean Scope

Use for non-trivial implementation work or when explicitly invoked. Skip a formal spec for trivial, mechanical edits unless the user asks. Read-only inspection and drafting the proposed scope are allowed before approval; do not change product code, configuration, or other implementation files until the user approves the spec. An explicit request to implement does not by itself approve a new spec created by this skill.

## Skill level

Resolve this skill's level from the user's request: `standard`, `high`, or `ultra`. If no level is requested, use `standard`; the existing workflow below remains the baseline. Natural-language requests such as "scope high" or "use ultra for all three skills" are sufficient; no new runtime command is required. A request for one skill does not raise the others. Keep the selection for this work until the user changes it; a later skill-specific request overrides an earlier group request. State the effective level briefly when starting the skill. If the request is ambiguous or names an unsupported level, clarify rather than silently substituting one.

Levels are optional skill capabilities, separate from workflow mode, Task Contract quality, budget, model, execution routing and review depth. Do not change those settings or spawn agents because of a skill level. Existing risk, approval, evidence and review requirements apply at every level. Do not silently lower a requested level; report unavailable evidence or constraints explicitly.

Higher levels add relevant detail, questions and evidence; they do not expand the user's intended scope or grant implementation or external-write authority. Reuse confirmed decisions. When handing off to scope, research or grill, preserve any user-selected level for the destination skill; otherwise it starts at `standard`. Feed findings back into the scope and decision summary, reopening only decisions affected by new evidence or a material conflict. In tracker/full mode, keep levels and findings in the existing owning tracker; in standard mode, keep them in the conversation.

### Scope depth

- **standard** — Use the existing draft and scope-protection workflow below.
- **high** — Add to standard: break the work into actors, user flows and individual behaviors. Specify inclusions, exclusions, business rules, dependencies and boundaries for each relevant part. Map each behavior to observable acceptance criteria and its validation. Use grill to clarify missing requirements rather than inventing them; use research where alternatives affect the scope.
- **ultra** — Add to high: detail every material part, including relevant states/transitions, edge cases, failures, recovery, exceptions and interactions between flows/components. Check cross-part consistency and trace requirements through behavior, acceptance and validation. Define relevant invariants and rollout/migration/rollback constraints where the work needs them. Iterate with grill/research until material ambiguity is resolved or explicitly blocked/deferred. Do not turn implementation minutiae into new requirements.

At high/ultra, show the user the detailed scope with confirmed decisions, assumptions, open points and exclusions clearly distinguished. More detail must narrow interpretation, not add unrequested features. Stop when acceptance is observable, material ambiguities/conflicts are resolved or explicitly identified, and every important behavior has a validation path. Preserve the approval boundary below; research findings that materially change an approved scope require matching approval before dependent work.

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
