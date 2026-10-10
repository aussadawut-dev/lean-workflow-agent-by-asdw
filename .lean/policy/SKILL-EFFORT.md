# Skill procedure intensity

`/lean-skill-effort` controls how thoroughly Lean procedures perform their particular jobs. Skill effort means procedure intensity, not model reasoning effort. Both Codex and Claude use this policy and the same repository settings.

## Selection

Read `.lean/skill-effort.json` in the selected record root when a Lean skill starts, if present. Its `default` applies to all Lean skills; its `skills` object contains named overrides. Missing settings mean `standard`. Resolve the effective level in this order: the user's latest explicit selection for this skill in the current work, its saved override, the saved default, then `standard`. A later explicit group selection replaces earlier individual selections for that group. State the effective level briefly and retain task selections in the owning tracker or conversation. Invalid settings or unsupported levels must be reported, not silently replaced.

State the effective procedure level briefly when starting a skill and again on a handoff when it differs. Keep the existing Task Contract format; procedure intensity does not add a gate mode.

Run `python3 .lean/scripts/skill_effort.py` to inspect saved levels. Like workflow/catalog commands, it resolves the active submodule's record root; `--root <record-root>` overrides selection. Invalid target context blocks without falling back. Skill names come from the workflow root, while settings belong to the project record root. The command accepts `standard|high|ultra|reset` and an optional full skill name. Without a skill name, setting a level applies to all skills and clears saved overrides; `reset` removes saved settings and returns to the standard default. For a named skill, setting a level creates an override and `reset` removes that override so it inherits the default. Only an explicit request to set/reset authorizes persistence; a task-specific natural-language level stays in that task's records. Read saved settings again on the next invocation; a discovery reload is needed only to discover a newly installed skill.

## What changes

| Skill | standard | high adds | ultra adds to high |
|---|---|---|---|
| lean-scope | Clear goal, boundaries and observable acceptance | Actors, flows, rules and validation for each relevant behavior | Material states, edge cases, recovery and cross-flow consistency |
| lean-research | Bounded comparison with traceable evidence | Broader relevant approaches and cross-checks of decisive claims | Deeper leading-candidate analysis, contradictory evidence and conditional recommendations |
| lean-grill | Resolve material open decisions | Walk relevant requirements and concrete failure scenarios | Follow up on consequential answers and check cross-part contradictions |
| lean-review | Required review depth and acceptance coverage | Trace the shipping changes through callers, interfaces and relevant failure paths | Challenge consequential assumptions and inspect cross-component invariants and regression gaps |
| lean-gate | Verify every required completion condition | Map each acceptance criterion to current evidence and expose gaps or stale coverage | Cross-check consistency across scope, tests, review, tracker and queue; identify unsupported completion claims |
| Other Lean skills | Existing skill procedure | Examine relevant dependencies, constraints and evidence in more detail | Cross-check consequential interactions, failure/recovery paths and unresolved contradictions within that skill's purpose |

Use the more specific depth guidance in scope/research/grill alongside this policy. Higher intensity must improve relevant coverage or evidence, not inflate output or meet an arbitrary source/question quota. Research separates verified facts, source claims, inference and uncertainty; diverse relevant approaches and accurate synthesis matter more than source count. Stop once the task-specific outcome is supported or the remaining gaps are explicit.

## Boundaries

Intensity is separate from model reasoning effort, Task Contract quality, risk, required review depth, budget, workflow mode and execution routing. It does not switch models, edit runtime `effort` frontmatter, authorize paid usage, spawn agents, expand accepted scope, or grant external-write/publication permissions. Model settings still follow MODELS.md. At every intensity, retain required tests, independent review where mandated, review round limits, gate commands and the project's existing gate policy. Standard never lowers those obligations; high/ultra never imply they passed. Reuse valid evidence for an unchanged shipping state rather than rerunning checks just to increase intensity.
