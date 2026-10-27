# Task

Implement `apply_patch(original, patch)` in `patcher.py`: apply a unified diff for one file to the text
`original` and return the new text. Standard library only; keep the signature.

Rules:

1. Lines before the first hunk (`diff --git`, `index`, `---`, `+++`, anything else) are ignored.
2. A hunk starts with `@@ -A[,B] +C[,D] @@` optionally followed by section text. An omitted count means 1.
   Any other line starting with `@@` at a hunk boundary is malformed: raise `ValueError`.
   `A`/`C` are 1-based start lines; a count of 0 means the start names the line *before* the change
   (so `-0,0` inserts at the top).
3. Body lines start with `' '` (context), `'-'` (removed) or `'+'` (added). A line `\ No newline at end of file`
   applies to the line just before it: that line has no trailing newline (on the old side if it follows a
   context/removed line, on the new side if it follows an added line; after a context line, both sides).
   An empty body line (no prefix at all) counts as an empty context line.
4. The number of context+removed lines must equal B and context+added must equal D; otherwise raise
   `ValueError`.
5. Hunks apply in order. A hunk's old lines (context+removed) must match the original exactly (line text and
   whether it ends with a newline) at its stated position after the shift caused by earlier hunks. If they do
   not match there, search for the nearest position where they match, trying offsets +1, -1, +2, -2, ...;
   never before the end of the previous hunk. No match anywhere: raise `ValueError`.
6. Line endings are `\n` only.

`python3 -m unittest discover -s tests` runs the visible tests.
