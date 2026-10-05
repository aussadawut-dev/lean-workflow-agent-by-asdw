---
name: lean-research
description: Find and compare in-repository or external approaches with traceable evidence, explain trade-offs, and recommend options when a decision has meaningful alternatives.
user-invocable: false
---

# Lean Research

Use this skill when a task needs evidence about prior work, competing designs, libraries, projects, standards, or ways to extend the current work. Skip it for routine changes with an already settled approach or a direct factual question.

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
