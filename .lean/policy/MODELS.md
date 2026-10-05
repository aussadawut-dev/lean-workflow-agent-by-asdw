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

These are starting points for settings the agent can select. Use the current session settings when
the runtime does not let the agent change them; do not interrupt routine work just to match the
table. Use a supported effort level at or above the starting point when useful; if none is
available, assess the result against the quality floor. Check the actual options exposed by Claude
or Codex before selecting a subagent. `CHEAP` favors the least
costly capable option, `BALANCED` uses the normal starting point, and `EXPENSIVE` permits more spend
when justified; none removes tests, validation, or required review. If the quality floor cannot be
met within the budget, report the constraint.

## Independent review

`HIGH` review depth requires an independent reviewer and the checks in `REVIEW.md`. Select the least
costly reviewer capable of examining the boundary at that depth. A fresh context that receives the
Task Contract and diff, without the author's reasoning, provides independence; the reviewer does
not have to use a stronger model than the author. Raise its effort or model when the boundary is
complex or review evidence shows a reasoning limit. Report when the review was not independent.

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

Classify a failure before changing model or effort. Repair implementation, missing context, tools,
or permissions at their source. For a demonstrated reasoning limit, increase one supported effort
level first if the model remains capable; then consider a stronger model if needed. Change one
variable per retry, record the reason, and stop at the review round cap in `REVIEW.md`. Do not spend
more merely because a task is long, and never lower the quality floor to save budget.

## Project catalog refresh

Use `/lean-model-update codex|claude|all` when a refresh is requested. It combines accepted scope,
source-grounded research and decision grilling, then previews a versioned project catalog.
An explicit apply updates catalog evidence only; it does not switch a session, rewrite global
settings, authorize paid usage or change the shared reviewer definition.

Consult the optional `.lean/model-catalog.json` alongside the current runtime's exposed options.
Missing catalog leaves normal selection unchanged. Stale, retired or unknown-availability entries
are not proof of eligibility; recheck the runtime and sources before selecting a replacement.
Preserve explicit model choices and report an unavailable choice rather than silently replacing it.
Provider IDs belong in project evidence, not this portable policy. Requested settings, observed
availability and reported backend settings remain distinct. Premium evidence, budget, independent
review and the quality floor still apply even to a newly documented model.
