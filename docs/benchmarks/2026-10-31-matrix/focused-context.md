## Focused source investigation

Use this read strategy for an analysis-only task. Keep every applicable instruction, safety boundary, dependency, validation requirement and review depth.

- Start from the requested questions. Maintain a small evidence checklist; stop exploring when each question has implementation evidence, relevant test evidence and an explicit limitation. Do not expand into adjacent features merely to make the answer longer.
- Read mandatory startup documents together once. Reuse their instructions rather than fetching their routed policy bodies to restate requirements already present. Load a routed policy only when a procedure or unresolved rule actually requires it. Keep required contract and progress operations; combine independent reads with bookkeeping when permitted.
- Locate filenames and symbols before reading source. Batch independent searches and excerpts in one tool call. Use quoted paths and globs; tolerate an expected no-match search explicitly so it does not hide useful results.
- Read complete small modules and complete relevant function/test blocks from larger files. Prefer symbol-bound excerpts with path and line numbers. When an excerpt is incomplete, expand it before making a claim. Avoid dumping entire large registrars, test suites or schema files for a single symbol.
- Follow imports, wrappers, permission checks, persistence and callers wherever they change the answer. A narrow initial search is not a file allowlist. If a security/data conclusion depends on a boundary, inspect that boundary even if more context is needed.
- Do not duplicate source text in commentary or re-read unchanged evidence for a summary. Give one concise evidence-based answer at the end. Distinguish source inspection, proposed checks and checks actually run. Never trade correctness, uncertainty disclosure or safety for a token limit.
