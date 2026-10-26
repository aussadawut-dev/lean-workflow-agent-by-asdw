# Skills

[Back to README](../README.md)

Eleven procedures live in `.lean/skills/`; Claude finds them through `.claude/skills/` (`/name`), Codex through `.agents/skills/` (`$name`), and agy by reading the `SKILL.md`.

| Skill | Use it to |
|---|---|
| `lean-init` | choose mode and execution, check the model list, fill PROJECT.md from real facts |
| `lean-task` | run a task through every phase with a progress bar |
| `lean-scope` | agree a scope with observable acceptance; pause only when it must |
| `lean-research` | compare real alternatives with traceable evidence |
| `lean-grill` | resolve the decisions that would change the result |
| `lean-agents` | spawn agents: alone for maximum parallel tasks, `<model> xN` for up to N at once on that model |
| `lean-review` | review at the required depth; HIGH uses an independent reviewer |
| `lean-gate` | run the Quality Gate and decide DONE, BLOCKED or FAILED |
| `lean-effort` | set procedure intensity: `standard`, `high`, `ultra` |
| `lean-update` | update Lean from a pinned release with a reviewed plan and rollback |
| `lean-target` | keep an application in its own repository as a submodule under `targets/` |

Intensity deepens scope, research, grill, review and gate procedures; it never changes the model or its reasoning effort ([SKILL-EFFORT.md](../.lean/policy/SKILL-EFFORT.md)). Project-specific skills may sit beside the Lean links in either discovery folder.
