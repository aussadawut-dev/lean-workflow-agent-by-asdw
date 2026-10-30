---
name: lean-scope
description: Draft a spec for non-trivial work, continue on a clear request, wait for approval only when the request is ambiguous, a material decision is open, risk is HIGH or only a spec was asked for, and stop when changes leave the agreed scope.
user-invocable: true
argument-hint: "<work to scope>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md` (selection, handoffs and boundaries apply to every level); keep model reasoning effort separate.

# Lean Scope

Use for non-trivial implementation work or when explicitly invoked. Skip a formal spec for trivial, mechanical edits unless the user asks. A clear implementation request approves the scope that matches it: show the draft and continue without waiting for a reply. Wait for approval before changing product code, configuration or other implementation files only when the request is ambiguous in a way that changes the work, a material decision is unresolved (use `lean-grill`), the Task Contract risk is HIGH, or the user asked for a spec or analysis only; read-only inspection and drafting are always allowed. Run `python3 .lean/bin/lean progress set scope`.

## Scope depth

- **standard** — The draft and scope-protection workflow below.
- **high** — Add: break the work into actors, user flows and individual behaviors. Specify inclusions, exclusions, business rules, dependencies and boundaries for each relevant part. Map each behavior to observable acceptance criteria and its validation. Use grill to clarify missing requirements rather than inventing them; use research where alternatives affect the scope.
- **ultra** — Add to high: detail every material part, including relevant states/transitions, edge cases, failures, recovery, exceptions and interactions between flows/components. Check cross-part consistency and trace requirements through behavior, acceptance and validation. Define invariants and rollout/migration/rollback constraints where the work needs them. Iterate with grill/research until material ambiguity is resolved or explicitly blocked/deferred. Do not turn implementation minutiae into new requirements.

At high/ultra, show the detailed scope with confirmed decisions, assumptions, open points and exclusions clearly distinguished. Stop when acceptance is observable, material ambiguities are resolved or explicitly identified, and every important behavior has a validation path.

## Draft the scope

Read the relevant `AGENTS.md`, project context and current tracker. Reuse a user-approved scope already recorded for this work; do not ask the user to approve it again. Draft a new scope or a material amendment only when no matching approved scope exists. If choosing an approach needs evidence, use `lean-research`; if a material decision remains open, use `lean-grill` before dependent implementation.

Write a concise draft with:

- Goal and intended user-visible outcome.
- In-scope behavior and explicit non-goals.
- Observable acceptance criteria and relevant validation.
- Constraints, dependencies, assumptions, and material open questions.
- Likely affected components or files when repository evidence makes them clear; label uncertain locations as estimates.
- For work that splits into independent parts, the task list a spawn plan would use (ids, owned files, size 3S-3XL, dependencies), so `/lean-agents` can run it without re-planning.

Show the draft. When the request already approves it, continue with the work; a later correction amends the scope. Otherwise ask for approval or corrections and pause: silence, elapsed time or approval of a different decision is not scope approval. If the user requested analysis or a spec only, return the draft without implementing it.

## Protect the approved scope

Once accepted, record the scope in the owning tracker before implementation when tracker mode requires it, and keep a simple scope ledger against the approved goal and acceptance criteria. Continue with routine implementation choices that fit the scope. If a necessary change would add behavior, alter acceptance, expand affected areas materially, or change a recorded decision, stop that dependent work and ask first: state the proposed delta, why it is needed, its impact on effort or risk, and a recommended option. Independent work within scope may continue. When the user approves a scope change, update the tracker before continuing. At completion, map each acceptance criterion to evidence and name any deferred work.

This skill defines and guards scope; it does not authorize publication, deployment or unrelated external writes.

## Continuing intake

When requirements arrive during work, use the bounded intake and batch rules in `.lean/policy/WORKFLOW.md`: classify and trace each request, queue new features, checkpoint explicit interruptions, freeze scope for review, and keep implementation/review/gate readiness separate. Keep tracker/direct as the starting path; the optional ledger does not require full mode or authorize material trade-offs.
