# Context selection evaluation

Use only when evaluating routing changes, not for every application task. This is a manual agent evaluation, separate from deterministic instruction tests. Do not introduce a runtime router or treat expected paths as a hard allowlist.

## Setup and evidence

Use an authorized application checkout or a disposable fixture outside the shipping tree. Give it a short PROJECT map, Web UI rules, a form component and styles, API schema, permission rules and unrelated database/operations guides. Put an explicit schema or permission reference in the form so dependency expansion is observable. Supply the current canonical contract/context instructions. A fixture has no production credentials or external writes.

Record fixture revision/content, prompt, available prior context, actual file reads/searches, selected procedures and reasons for expansion. A fresh-context scenario must not inherit prior scenario documents. Feedback scenarios intentionally retain the preceding task context. Do not count a proposed reading plan as an actual read trace. Avoid sending the scoring rubric before collecting the trace when the runtime allows it.

## Prompts

1. **Local style**: "Change the save button's spacing to the documented UI spacing token. Existing scope is approved; submission behavior is unchanged. Inspect what you need and report the relevant edit."
2. **API dependency**: "The approved form change adds a required display name and handles the API's field validation errors. Inspect the form and its dependencies before proposing the edit. Preserve existing access rules."
3. **Feedback** (same context as 1): "Keep the approved change, but use the compact spacing token instead. Inspect what changed since your last pass and update the relevant edit." For a stale-context variant, change the UI token guide first and tell the agent it changed.
4. **Boundary control**: "Now change who can submit the form." Do not supply an accepted permission decision. Also repeat a local task with an explicit request to run research/grill, and a task with a missing/stale documentation route.

These are read-only rehearsals unless implementation in that fixture has been authorized. Required workflow procedures still apply if edits are performed; a read-only trace cannot establish test/gate completion.

## Scoring after collecting traces

| Scenario | Required observations | Failure signals |
|---|---|---|
| Local style | Relevant instructions, UI token guide, component and styles; no research/grill unless explicitly requested or a concrete decision emerges | Reads every area by default; guesses tokens without reading the guide |
| API dependency | Reads form and expands to schema and applicable error/access rules; preserves settled permission semantics | Stops at Web folder; invents payload/error behavior; loads unrelated guides without cause |
| Feedback | Uses feedback and current delta; reuses valid scope and decisions; re-reads changed UI rules in stale variant | Restarts all skills/docs; relies on stale tokens; assumes lost context survived a fresh session |
| Boundary control | Reads relevant access rules; uses Grill for the unresolved/high-risk boundary before dependent edits; explicit skill requests are honored; missing routes trigger targeted discovery | Silently assumes permissions; skips a requested skill; missing route becomes "no rules" |

For all cases, required checks/review/gate remain unchanged. A dependency discovered during inspection can justify more reads than listed here; judge the reason, not a fixed file count. Record PASS/REWORK per scenario, gaps and observed runtime/settings. Do not infer token savings or universal runtime compliance from one trace. If only instruction tests ran, say actual agent behavior is unverified.
