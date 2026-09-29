# Context

Use the smallest sufficient context. Load progressively.

## Documentation staircase

```
.agent/PROJECT.md
      |
<area>/README.md        (if it exists)
      |
<area>/<sub>/README.md  (if it exists)
      |
source
```

Follow routes recorded in `PROJECT.md`. Area READMEs are optional and owned by the project; do not create hierarchy in advance.

## Rules

- Read the exact target when known; skip routes that add nothing.
- Expand context only when the task or evidence requires it.
- On retry or rework, use **delta context** (what changed and why), not a full rebuild.
- Do not load every `.agent/` file by default.
- Record newly learned conventions in `PROJECT.md`.
