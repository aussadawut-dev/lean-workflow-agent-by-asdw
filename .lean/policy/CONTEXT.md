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

Choose by affected behavior; follow dependencies across area boundaries. When a form change affects payload, validation, error handling or access, expand to the API contract/schema and permission rules that govern it. Read database or operational documents only when an affected dependency requires them. Folder names are starting points, not an allowlist.

## Select procedures

Skill discovery metadata is an index, not a request to activate every skill. Load a skill body when its procedure is needed, and its references only for the relevant step. Explicitly requested skills still run.

- Scope: reuse matching accepted scope; resolve approval only for new scope or a material expansion.
- Research: use when meaningful alternatives or missing evidence could change the decision; do not rerun settled research without a relevant change.
- Grill: use for unresolved material decisions or required high-risk boundaries; clear accepted work does not reopen decisions just because another edit is requested.
- Review and gate: run at the required depth and completion boundary. Selecting context does not select or reduce tests, review depth or Quality Gate commands.

## Continue with delta context

On feedback or rework, start from feedback, current diff and affected dependencies. Reuse accepted scope, confirmed decisions and already-read context while they remain valid. Re-read changed files, stale evidence, conflicting requirements or newly affected dependencies; do not rebuild all context or restart every skill. After compaction or a new session, run `lean mode context` and recover the minimum relevant records and current source rather than assuming missing prior context is available.

## Rules

- Read the exact target when known; skip routes that add nothing.
- Expand context only when the task or evidence requires it; record a brief reason for a non-obvious expansion in the tracker or session evidence.
- Do not load every `.lean/` file by default.
- Record newly learned conventions in `.lean/PROJECT.md`.
