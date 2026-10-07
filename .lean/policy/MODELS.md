# Models and effort

Choose the least costly available model and effort likely to satisfy the Task Contract. Risk and
quality set the required work and review depth; budget guides optional spend. Repository mode
(`standard`, `tracker`, or `full`) does not change model selection. Do not pin provider model IDs in
this portable policy.

## Starting point

| Work | Model capability | Effort |
|---|---|---|
| Mechanical, well-specified work (locate, rename, format) | Economical available model | Low |
| Normal implementation or focused review | Current/default capable model | Medium |
| Hard reasoning, conflicting evidence, or a complex security/data boundary | Capable model for that task | High when the added reasoning is useful |

Use current settings when the runtime cannot change them; do not interrupt routine work to match the table. Check actual model/effort options before dispatch. Use supported effort at or above the starting point when useful, or assess the available setting against the quality floor. `CHEAP` favors economical capable options, `BALANCED` uses the normal starting point, and `EXPENSIVE` allows justified optional spend. None removes tests, validation or required review; report an unmet floor rather than lowering it.

## Independent review

`HIGH` review uses an independent context with the Task Contract and diff, without author reasoning, under `REVIEW.md`. Choose the least costly capable reviewer; a stronger model is not required. Escalate only for useful boundary analysis or demonstrated reasoning limits. Report missing independence.

## Runtime control

- Claude: the session model and effort follow the user's/runtime's settings. The `reviewer`
  subagent has `model: inherit` and inherits session effort. Claude can override its model for one
  invocation when supported. Raise reviewer effort only through a supported runtime control; do
  not edit the shared subagent definition for one task.
- Codex: follow the session settings for the main agent. For an independent review, use a subagent
  or fresh session; set its model and reasoning effort only when the available tool supports them
  and the choice has a reason. Otherwise use the available defaults.
- Never claim to have changed the main session or a subagent setting unless the runtime confirms it.
  If a desired setting is unavailable, use a capable available option. If none can meet the floor,
  report `BLOCKED` with the limitation. Recommend a user-controlled session change only when the
  current setting threatens the quality floor or repeated reasoning failure warrants it.

## Premium dispatch evidence

Before selecting a premium model or initiating additional usage billing, record the required outcome, material constraints, cheaper available option considered and concrete task-specific evidence that it cannot meet acceptance/quality. Provider names and prices belong to runtime evidence, not portable rules. A HIGH label, preference or broad complexity claim is insufficient. Use a cheaper capable option when that evidence is absent; otherwise gather it or report the constraint. User authorization is still required for additional paid usage; a dispatch justification is not billing permission.

## Escalation

Classify failure first: fix implementation, context, tools or permissions at their source. For a demonstrated reasoning limit, raise one supported effort level before changing to a stronger model. Change one variable per retry, record why and obey `REVIEW.md`'s round cap. Task length alone does not justify escalation; budget never lowers quality.

## Project catalog refresh

Use `/lean-model-update codex|claude|all` only when requested; enable its optional maintenance discovery if needed. Research and preview a versioned project-owned catalog, then apply only accepted changes. This never changes session/global settings, reviewer definitions or billing authorization.

Consult optional `.lean/model-catalog.json` alongside current runtime options. A missing catalog changes nothing. Stale, retired or unknown-availability entries require rechecking; preserve explicit model choices and report unavailable ones. Provider IDs/prices belong to evidence, not portable rules. Distinguish requested settings, observed availability and reported backend settings. Premium evidence, budget, independence and quality requirements still apply.
