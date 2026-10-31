# Proposed runtime prototype: preserve quality, reduce repeated context

Proposal only. The 48-trial study has not demonstrated >=20% savings across all four levels; no shared Lean runtime, guard, policy or Casetodian source has been changed. More prose/eager source packets are not recommended as a default based on this evidence.

## Outcome and boundaries

Build an opt-in runtime path that reduces repeated LLM context while retaining contract binding, target-root validation, scope ownership, safety checks, deterministic validation, required semantic review and the full gate. Primary target remains >=20% actual input+output versus 4.17.0 in all four frozen difficulties, with no quality loss. The target is a test to pass, not a guaranteed property or quota conversion.

This is HIGH-risk implementation because it touches the command entry point/contract guard and canonical workflow routing. It needs a separate accepted implementation contract and independent HIGH review. The current work authorizes the study and this concrete proposal; it does not silently accept a new guard declaration syntax or a worker-policy exception.

## Three bounded slices

1. **Atomic startup.** Prototype one command carrying a literal Task Contract that validates it, resolves the three roots, reads configured mode, records scope progress and returns a small structured context object. The guard recognizes only that exact declaration form, never an arbitrary chained shell command. Preserve superseded-session refusal, target errors, symlink checks, locks, mode/lease ownership and provider parity. No pre-contract product writes become authorized. A read-only preview must remain read-only.
2. **Cited source retrieval.** Provide exact path/line or complete-symbol views with explicitly bounded output, known test/reference links, continuation metadata and visible omissions. Retrieve at the step that needs the evidence. Do not inject an entire repository/packet at startup or claim a regex dependency search is complete. Source bytes and citations must verify against the same Git revision. Missing material auth/data/network dependencies still require expansion.
3. **Bounded worker contexts.** Keep full workset rules/validation/review in the Controller and dispatch small read-only source tasks with the exact contract, permitted scope, relevant source facts, checks, limitations and return schema. Define the worker's applicable rules explicitly; do not silently exempt it from required instructions. Test a fresh bounded context per component. Count all Controller, worker, review, retry and handoff tokens in the candidate's end-to-end metric, not just a cheap worker's usage. Preserve subscription authentication and removal of metered API keys.

The token causes suggested by current traces are hypotheses. Fewer CLI commands alone did not establish lower tokens; the prototype must measure actual provider counters and validate quality rather than rely on that proxy.

## Validation and decision gate

- Before any runtime change, add failing regressions for its exact new behavior and enforcement edges. Validate malformed/expanded/chained declarations, stale/superseded sessions, invalid targets, symlink refusal, read-only preview, and unchanged gate/review requirements.
- Run the affected unit/hooks/e2e suites plus deterministic checks, independent HIGH review and the shared full gate. No weakening of tests, acceptance, the gate or source-scope safeguards.
- Start with one difficult representative task to reject an ineffective mechanism cheaply; only a successful candidate expands to the complete four-level bank.
- Repeat with counterbalanced order and retain every failure/unknown token bill. Fix the candidate before confirmation; do not tune against confirmation outcomes without labelling another exploratory cycle.
- Confirm on unseen tasks, including an implementation with meaningful tests in a disposable environment where available. The present source-only rubric does not establish implementation or deployment quality.
- Report actual input/cached/uncached/output/reasoning counters, complete end-to-end candidate cost, independent rubric results and unavailable quota attribution. Never double-count cache/reasoning subsets or price an interrupted trial at zero.

Use an opt-in experimental flag until the target and safety checks pass. Publication, rollout and default changes are separate decisions. If the mechanism cannot meet quality and token targets together, keep the current safeguards and report the failure.

## Required decision

Accept or revise the three runtime interfaces and Controller/worker responsibility boundary before implementation. The smallest initial slice is atomic startup plus exact cited reads; add delegation only if it improves measured end-to-end cost. Model/effort remains fixed within each task while testing the mechanism.
