---
name: lean-research
description: Find and compare approaches with traceable evidence, explain trade-offs, and recommend when a decision has real alternatives.
user-invocable: true
argument-hint: "<decision or question>"
---

Input: `$ARGUMENTS` means the explicit invocation arguments, or the current user task when the runtime does not substitute it. Resolve this skill's procedure intensity under `.lean/policy/SKILL-EFFORT.md` (selection, handoffs and boundaries apply to every level); keep model reasoning effort separate.

# Lean Research

Use this skill when a task needs evidence about prior work, competing designs, libraries, projects, standards, or ways to extend the current work. Skip it for routine changes with an already settled approach or a direct factual question.

## Research depth

- **standard** — A bounded shortlist, usually 2–5 meaningful options, compared with evidence.
- **high** — Add: broaden discovery to more relevant vendors, projects or approaches. Compare capabilities, fit, limitations and decision-relevant costs/compatibility with the same criteria. Verify decisive claims across multiple sources where available; distinguish primary documentation from independent evidence and marketing. Explain why candidates were shortlisted or excluded, and identify evidence gaps that could change the recommendation.
- **ultra** — Add to high: survey the option space more broadly, then investigate the strongest candidates in depth, including materially different approaches. Cross-check decisive claims and seek contradictory evidence. Identify the conditions under which each leading option is preferable and where uncertainty prevents a reliable ranking. Propose a targeted validation when documents cannot settle a decisive question; perform it only within existing authority.

At high/ultra, distinguish candidate breadth from source depth. Do not count syndicated copies as independent corroboration or one vendor's pages as multiple vendors. Record source dates/versions when relevant, link decisive claims, and separate verified facts, vendor claims, inferences and unknowns. If only a few relevant options or sources exist, explain the limit rather than inventing breadth or certainty.

## Workflow

1. State the decision to support, the user's goal, and the constraints that affect it. Read the relevant repository context and current tracker before searching broadly.
2. Build a bounded shortlist. Include the current approach or no change when useful. Search only far enough to identify meaningful differences and evidence that could change the recommendation.
3. Prefer direct project code, tests and docs for repository claims. For external claims, prefer official documentation, specifications, release notes and source code; check local tools directly when they are installed. Record the date and version when facts may change. Label claims you could not check as unverified.
4. Compare options against the same criteria, chosen from the user's actual priorities. Separate verified facts from inferences and recommendations. Link material claims to repository paths or direct sources.
5. Explain what each advantage enables and its trade-offs. Recommend which option is better for which goal; do not claim a universal winner. Avoid arbitrary numeric scores.

## Report

Give a concise decision summary, scope and assumptions, comparison of options, evidence-backed strengths and trade-offs, a conditional recommendation, and remaining uncertainties or validation steps. Call out cost, licensing, compatibility, security or maintenance only where they affect the decision; never imply permission to add a paid service or dependency.

In `tracker` or `full` mode, record findings and sources in the owning TCK document. If implementation follows, hand the selected approach to `lean-scope`; use `lean-grill` for material decisions that remain open. This skill gathers evidence and recommends—it does not implement, approve scope, or authorize external writes.
