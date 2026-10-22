# Context

Use the smallest sufficient context. Load progressively.

## Documentation staircase

```
.lean/PROJECT.md
      |
<area>/README.md        (if it exists)
      |
<area>/<sub>/README.md  (if it exists)
      |
source
```

Follow routes recorded in `.lean/PROJECT.md`. Area READMEs are optional and owned by the project; do not create hierarchy in advance.

## Select by impact

Keep PROJECT.md a short map of project facts, commands, risks and documentation routes. Put detailed area rules and historical validation notes in focused project-owned documents. Preserve the configured gate and High-risk areas when shortening it. Do not invent Web/API/Database sections for a project that has none.

Start with the user's goal, accepted scope and known target paths. Read the relevant instructions, then the closest useful area guide and source. For an unfamiliar cross-area task, a broader initial read may be necessary; narrow subsequent reads once the affected areas are known. Missing or stale routes require targeted file/reference searches, not loading every document or assuming the requirement does not exist.

Choose by affected behavior; follow dependencies across area boundaries. For a style-only web change, start with applicable UI rules, component and styles. When a form change affects payload, validation, error handling or access, expand to the API contract/schema and permission rules that govern it. Read database or operational documents only when an affected dependency requires them. When `.lean/PROJECT.md` (or `record_root` for a submodule) routes to accepted project standards, load only the standard routes matching affected behavior or signals—such as module-boundary and dependency-direction rules when adding, moving or importing across modules, and i18n or locale glossary rules when adding or changing user-facing copy or locale files. Folder names are starting points, not an allowlist.

## Select procedures

Skill discovery metadata is an index, not a request to activate every skill. Load a skill body when its procedure is needed, and its references only for the relevant step. Explicitly requested skills still run. Preserve required scope, configured execution, mandatory high-risk Grill, review and completion procedures.

- Scope: reuse matching accepted scope; resolve approval only for new scope or a material expansion.
- Research: use when meaningful alternatives or missing evidence could change the decision; do not rerun settled research without a relevant change.
- Grill: use for unresolved material decisions or required high-risk boundaries; clear accepted work does not reopen decisions just because another edit is requested.
- Review and gate: run at the required depth and completion boundary. Selecting context does not select or reduce tests, review depth or Quality Gate commands.

Intensity deepens a selected procedure; it does not activate others. Existing required procedures still apply at every intensity.

## Continue with delta context

On feedback or rework, start from feedback, current diff and affected dependencies. Reuse accepted scope, confirmed decisions and already-read context while they remain valid. Re-read changed files, stale evidence, conflicting requirements or newly affected dependencies; do not rebuild all context or restart every skill. Material scope changes still need approval. After compaction or a new session, recover the minimum relevant records and current source rather than assuming missing prior context is available.

Record a brief reason for a non-obvious context expansion in the existing session/tracker evidence. Do not create a mandatory read log for every file. Context selection limits additional reads; it cannot remove content already present in the runtime's conversation.

For a workflow routing change, evaluate representative read traces using `.lean/skills/lean-task/references/context-scenarios.md`. Instruction tests protect these rules but do not prove a future agent follows them.

## Rules

- Read the exact target when known; skip routes that add nothing.
- Expand context only when the task or evidence requires it.
- On retry or rework, use **delta context** (what changed and why), not a full rebuild.
- Do not load every `.lean/` file by default.
- Record newly learned conventions in `.lean/PROJECT.md`.
