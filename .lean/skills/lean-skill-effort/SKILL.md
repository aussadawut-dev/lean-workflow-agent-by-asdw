---
name: lean-skill-effort
description: Inspect or set Lean skill procedure intensity (standard, high, ultra), globally or per skill, shared by Codex and Claude. Use for /lean-skill-effort; separate from model reasoning effort.
user-invocable: true
argument-hint: "[standard|high|ultra|reset] [lean-skill-name]"
---

# Lean Skill Effort

Read `.lean/policy/SKILL-EFFORT.md`. This command controls thoroughness of task-specific procedures: scope definition, research breadth and accuracy, review coverage, and completion evidence.

No arguments: run `python3 .lean/scripts/skill_effort.py` and report saved levels. With an explicit level/reset and optional skill name: validate the arguments and pass them as separate literal arguments to that script. Do not execute arbitrary invocation text as shell code. Report the resulting effective level and whether it applies to all skills or a named skill.

Examples:

- `/lean-skill-effort high`: high procedure intensity for all Lean skills.
- `/lean-skill-effort ultra lean-research`: deeper and broader research for that skill.
- `/lean-skill-effort reset lean-research`: research inherits the saved default.
- `/lean-skill-effort reset`: all skills return to standard defaults.

The CLI resolves the active target's record root; pass `--root <record-root>` only for an explicit override. Inspect without arguments is read-only and never creates settings/runtime state. Settings are project-owned and are not release assets. Read updated settings on subsequent invocations. Task-specific natural-language selections override saved levels for that work without changing repository defaults. Never map these levels to model `medium/high/max` or rewrite skill frontmatter. Existing tests, review and completion requirements apply at every level.
