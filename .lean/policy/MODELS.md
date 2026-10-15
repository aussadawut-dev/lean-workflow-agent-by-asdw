# Models and effort

Model reasoning effort is separate from procedure intensity under `SKILL-EFFORT.md`; never translate standard/high/ultra procedure levels into runtime settings.

Choose the least costly available model and effort likely to satisfy the Task Contract. Risk and
quality set the required work and review depth; budget guides optional spend. Repository mode
(`standard`, `tracker`, or `full`) does not change model selection. Do not pin provider model IDs in
this portable policy.

## Spawn or finish in the session

Spawn only when required or cheaper. Required: delegated execution, HIGH independent review, or an explicit user request for workers. Otherwise compare total cost: finishing in the active session (context already loaded) versus a spawn (brief, cold re-reads, subagent work at its price, result handed back). Finish in the session when that costs less or about the same; spawn mainly for large, read-heavy work a cheaper model can do without the session's context.

## Starting point

| Work | Model capability | Effort |
|---|---|---|
| Mechanical, well-specified work (locate, rename, format) | Economical available model | Low |
| Normal implementation or focused review | Current/default capable model | Medium |
| Hard reasoning, conflicting evidence, or a complex security/data boundary | Capable model for that task | High when the added reasoning is useful |

Size each delegated task, reviewers included, by this table and pass the chosen model and effort on every spawn whose tool accepts them. Omitted settings inherit the session defaults, which are often heavier than delegated work. Inherit the session setting only when it already matches the row or the tool cannot set it, and record that reason. Projects may map the rows to concrete models in AGENTS.md Project additions or `.lean/model-catalog.json`. The active session's own settings stay with the user: use them when the runtime cannot change them, and do not interrupt routine work to switch them. Check actual model/effort options before dispatch. Use supported effort at or above the starting point when useful, or assess the available setting against the quality floor. `CHEAP` favors economical capable options, `BALANCED` uses the normal starting point, and `EXPENSIVE` allows justified optional spend. None removes tests, validation or required review; report an unmet floor rather than lowering it.

## Independent review

`HIGH` review uses an independent context with the Task Contract and diff, without author reasoning, under `REVIEW.md`. Choose the least costly capable reviewer; a stronger model is not required. Escalate only for useful boundary analysis or demonstrated reasoning limits. Report missing independence.

A wording-only diff may use an economical capable available reviewer model at its default or lower effort. A diff is wording-only when it changes only instruction or documentation prose, adds or removes no rule, and leaves unchanged every normative keyword (such as must, may, never, only, required and their negations), number, limit, YAML frontmatter, import, heading/anchor, code span or block, command, path, link, identifier, table layout, list hierarchy and order, gate marker and license notice. Any change to executable code, tests, hooks or configuration disqualifies the diff. Give the reviewer a before/after rule map covering every changed sentence. The reviewer checks each condition and verifies the map against the before/after text itself, not the author's summary. It returns `REWORK` when any condition fails, when the map is missing or incomplete, or when any rule's actor, trigger, action, ordering, limit, exception or authorization changed. That `REWORK` counts as a review round. After it, review the change, edited or unchanged, with a reviewer chosen by the normal starting point; an intended meaning change also needs its own Task Contract. This lowers reviewer cost only; the HIGH floor, independence, receipt and round limits stay unchanged.

## Runtime control

- Claude: the session model and effort follow the user's/runtime's settings. The `reviewer`
  subagent definition keeps `model: inherit` only as a portable fallback; pass the sized model,
  and effort when the Agent tool accepts it, on each invocation. Raise reviewer effort only through
  a supported runtime control; do not edit the shared subagent definition for one task.
- Codex: follow the session settings for the main agent. For workers and independent reviews, use a
  subagent or fresh session; when the spawn tool supports model and reasoning effort, set both by
  the starting point. Use the available defaults only when the tool cannot set them, and record that.
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
