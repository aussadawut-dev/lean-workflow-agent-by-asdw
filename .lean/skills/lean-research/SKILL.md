---
name: lean-research
description: Find and compare in-repository or external approaches with traceable evidence, explain trade-offs, and recommend options when a decision has meaningful alternatives.
user-invocable: true
argument-hint: "<research question>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it.

Apply `.lean/policy/SKILL-EFFORT.md` to resolve this skill's procedure intensity; keep model reasoning effort separate.

# Lean Research

Use this skill when a task needs evidence about prior work, competing designs, libraries, projects, standards, or ways to extend the current work. Skip it for routine changes with an already settled approach or a direct factual question.

## Skill level

Resolve `standard`, `high`, or `ultra` under `.lean/policy/SKILL-EFFORT.md`: the user's latest task selection, saved skill override, saved default, then `standard`; the existing workflow below remains the baseline. Natural-language requests such as "scope high" or "use ultra for all three skills" are sufficient; no new runtime command is required. A request for one skill does not raise the others. Keep the selection for this work until the user changes it; a later skill-specific request overrides an earlier group request. State the effective level briefly when starting the skill. If the request is ambiguous or names an unsupported level, clarify rather than silently substituting one.

Levels are optional skill capabilities, separate from workflow mode, Task Contract quality, budget, model, execution routing and review depth. Do not change those settings or spawn agents because of a skill level. Existing risk, approval, evidence and review requirements apply at every level. Do not silently lower a requested level; report unavailable evidence or constraints explicitly.

Higher levels add relevant detail, questions and evidence; they do not expand the user's intended scope or grant implementation or external-write authority. Reuse confirmed decisions. When handing off to scope, research or grill, preserve any user-selected level for the destination skill; otherwise resolve its saved override/default under SKILL-EFFORT. Feed findings back into the scope and decision summary, reopening only decisions affected by new evidence or a material conflict. In tracker/full mode, keep levels and findings in the existing owning tracker; in standard mode, keep them in the conversation.

### Research depth

- **standard** — Use the existing bounded shortlist and evidence-backed comparison below, usually 2–5 meaningful options.
- **high** — Add to standard: broaden discovery to more relevant vendors, projects or approaches than the initial shortlist where available. Compare capabilities, fit, limitations and decision-relevant costs/compatibility using the same criteria. Verify decisive claims across multiple sources where available; distinguish primary documentation from independent evidence and marketing. Explain why candidates were shortlisted or excluded, and identify evidence gaps that could change the recommendation.
- **ultra** — Add to high: survey the relevant option space more broadly, then investigate the strongest candidates in depth. Include materially different approaches where available. Compare detailed capabilities, constraints, integration and maintenance implications as relevant to this task. Cross-check decisive claims using multiple sources and seek contradictory evidence. Identify the conditions under which each leading option is preferable and where uncertainty prevents a reliable ranking. Propose a targeted validation when documents cannot settle a decisive question; perform it only within existing authority.

At high/ultra, distinguish candidate breadth (how many vendors/approaches) from source depth (how well each decisive claim is checked). Do not count syndicated copies as independent corroboration or one vendor's pages as multiple vendors. Record source dates/versions when relevant, link decisive claims, and separate verified facts, vendor claims, inferences and unknowns. Use a broader discovery set followed by a bounded comparison; the standard shortlist is not a cap on high/ultra discovery. Do not pad with irrelevant vendors or impose a fixed source quota. If only a few relevant options or sources exist, explain the limit rather than inventing breadth or certainty.

Report the compared candidates and exclusions, shared comparison criteria, claim-level evidence for decisive differences, recommendation with conditions, and unresolved gaps. Stop when evidence adequately distinguishes the options or the remaining uncertainty and next validation are explicit. Accuracy matters more than apparent completeness. Feed scope-changing findings to scope/grill; research does not authorize a prototype, dependency installation or external write.

## Workflow

1. State the decision to support, the user's goal, and the constraints that affect it. Read the relevant repository context and current tracker before searching broadly.
2. Build a bounded shortlist, usually 2–5 options. Include the current approach or no change when useful. Search only far enough to identify meaningful differences and evidence that could change the recommendation.
3. Prefer direct project code, tests, and docs for repository claims. For external claims, prefer official documentation, specifications, release notes, and source code. Use secondary sources for context. When facts may have changed, check current sources and record the date and relevant version or revision. If a source cannot be checked, label the claim unverified.
4. Compare options against the same criteria, chosen from the user's actual priorities. Separate verified facts from inferences and recommendations. Link material claims to repository paths or direct sources.
5. Explain what each advantage enables and its trade-offs. Recommend which option is better for which goal; do not claim a universal winner. Avoid arbitrary numeric scores. Use scores or weights only when the criteria are explicit and the evidence supports them.

## Report

Give a concise decision summary, scope and assumptions, comparison of options, evidence-backed strengths and trade-offs, a conditional recommendation, and remaining uncertainties or validation steps. Call out cost, licensing, compatibility, security, or maintenance only where they affect the decision; never imply permission to add a paid service or dependency.

In `tracker` or `full` mode, record findings and sources in the owning TCK document. Do not create a second tracker for research that is part of an existing workset. If implementation follows, hand the selected approach to `lean-scope`; use `lean-grill` for material decisions that remain open. This skill gathers evidence and recommends—it does not implement, approve scope, or authorize external writes.

$ARGUMENTS
