import re
HEAD = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
MARK = "\\ No newline at end of file"


def _split(text):
    lines = text.split("\n")
    out = [[l, True] for l in lines[:-1]]
    if lines[-1] != "":
        out.append([lines[-1], False])
    return out


def _hunks(patch):
    rows = patch.split("\n")
    if rows and rows[-1] == "":
        rows.pop()
    hunks, i = [], 0
    while i < len(rows) and not rows[i].startswith("@@"):
        i += 1
    while i < len(rows):
        m = HEAD.match(rows[i])
        if not m:
            raise ValueError("bad hunk header")
        a, b, c, d = int(m[1]), int(m[2] if m[2] is not None else 1), int(m[3]), int(m[4] if m[4] is not None else 1)
        i += 1
        old, new, last = [], [], None
        while i < len(rows) and not rows[i].startswith("@@"):
            r = rows[i]
            if r == MARK:
                if last in (" ", "-") and old:
                    old[-1][1] = False
                if last in (" ", "+") and new:
                    new[-1][1] = False
            else:
                kind, text = (r[0], r[1:]) if r else (" ", "")
                if kind not in " +-":
                    raise ValueError("bad body line")
                if kind in " -":
                    old.append([text, True])
                if kind in " +":
                    new.append([text, True])
                last = kind
            i += 1
        if len(old) != b or len(new) != d:
            raise ValueError("count mismatch")
        hunks.append((a, b, old, new))
    return hunks


def apply_patch(original, patch):
    lines = _split(original)
    shift, floor = 0, 0
    for a, b, old, new in _hunks(patch):
        start = (a - 1 if b else a) + shift
        found = None
        for k in range(0, len(lines) + 2):
            for pos in ((start,) if k == 0 else (start + k, start - k)):
                if pos >= floor and pos + len(old) <= len(lines) and lines[pos:pos + len(old)] == old:
                    found = pos
                    break
            if found is not None:
                break
        if found is None:
            raise ValueError("hunk does not apply")
        lines[found:found + len(old)] = [list(x) for x in new]
        shift += len(new) - len(old) + (found - start)
        floor = found + len(new)
    return "".join(t + ("\n" if nl else "") for t, nl in lines)
