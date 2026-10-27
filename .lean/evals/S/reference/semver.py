import re
_N = r"0|[1-9]\d*"
_ID = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
_RE = re.compile(rf"({_N})\.({_N})\.({_N})(?:-({_ID}(?:\.{_ID})*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?", re.ASCII)


def _parse(v):
    if not isinstance(v, str):
        raise TypeError("version must be str")
    m = _RE.fullmatch(v)
    if not m:
        raise ValueError(v)
    pre = m.group(4)
    return tuple(int(m.group(i)) for i in (1, 2, 3)), (pre.split(".") if pre else None)


def compare(a, b):
    (ca, pa), (cb, pb) = _parse(a), _parse(b)
    if ca != cb:
        return -1 if ca < cb else 1
    if pa == pb:
        return 0
    if pa is None:
        return 1
    if pb is None:
        return -1
    for x, y in zip(pa, pb):
        if x == y:
            continue
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            return -1 if int(x) < int(y) else 1
        if xn != yn:
            return -1 if xn else 1
        return -1 if x < y else 1
    return (len(pa) > len(pb)) - (len(pa) < len(pb))
