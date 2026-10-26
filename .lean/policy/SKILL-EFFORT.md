# Skill procedure intensity

`/lean-effort` controls how thoroughly Lean procedures perform their particular jobs. Skill effort means procedure intensity, not model reasoning effort. Every provider uses this policy and the same repository settings.

## Selection

Read `.lean/skill-effort.json` when a Lean skill starts, if present. Its `default` applies to all Lean skills; its `skills` object contains named overrides. Missing settings mean `standard`. Resolve the effective level in this order: the user's latest explicit selection for this skill in the current work, its saved override, the saved default, then `standard`. Natural-language requests ("scope high", "use ultra for all three skills") are enough; a request for one skill does not raise the others, and a later skill-specific request overrides an earlier group request. Keep the selection for this work until the user changes it. State the effective level briefly when starting a skill and on a handoff when it differs. Invalid settings or unsupported levels must be reported or clarified, not silently replaced.

`lean effort` inspects saved levels (read-only). `lean effort standard|high|ultra|reset [lean-skill-name]` saves them: without a skill name, a level applies to all skills and clears overrides, and `reset` returns to the standard default; with a name, a level creates an override and `reset` removes it. Only an explicit request to set or reset authorizes persistence; a task-specific level stays in that task's records.

## What changes

| Skill | standard | high adds | ultra adds to high |
|---|---|---|---|
| lean-scope | Clear goal, boundaries and observable acceptance | Actors, flows, rules and validation for each relevant behavior | Material states, edge cases, recovery and cross-flow consistency |
| lean-research | Bounded comparison with traceable evidence | Broader relevant approaches and cross-checks of decisive claims | Deeper leading-candidate analysis, contradictory evidence and conditional recommendations |
| lean-grill | Resolve material open decisions | Walk relevant requirements and concrete failure scenarios | Follow up on consequential answers and check cross-part contradictions |
| lean-review | Required review depth and acceptance coverage | Trace the shipping changes through callers, interfaces and relevant failure paths | Challenge consequential assumptions and inspect cross-component invariants and regression gaps |
| lean-gate | Verify every required completion condition | Map each acceptance criterion to current evidence and expose gaps or stale coverage | Cross-check consistency across scope, tests, review, tracker and queue; identify unsupported completion claims |
| Other Lean skills | Existing skill procedure | Examine relevant dependencies, constraints and evidence in more detail | Cross-check consequential interactions, failure/recovery paths and unresolved contradictions within that skill's purpose |

Higher intensity must improve relevant coverage or evidence, not inflate output or meet an arbitrary source or question quota. More detail narrows interpretation; it never adds unrequested features. Reuse confirmed decisions; when handing off between scope, research and grill, keep a user-selected level for the destination skill. Feed findings back into the scope and decision summary, reopening only decisions affected by new evidence or a material conflict. In tracker/full mode, keep levels and findings in the owning tracker; in standard mode, keep them in the conversation.

## Boundaries

Intensity is separate from model reasoning effort, Task Contract quality, risk, required review depth, budget, workflow mode and execution routing. It does not switch models, authorize paid usage, spawn agents, expand accepted scope, or grant external-write or publication permissions. At every intensity, retain required tests, independent review where mandated, review round limits, gate commands and the project's gate policy. Standard never lowers those obligations; high/ultra never imply they passed. Reuse valid evidence for an unchanged shipping state rather than rerunning checks just to increase intensity.
