"""Pure gate refusal rules: no file, Git, shell or transcript access.

Both gate hooks (Codex and shell) call gate_refusal and session_key, so the refusal count, the cap and the
session marker names are decided in one place.
"""

MAX_REFUSALS = 3  # quality-gate.sh `max_refusals`, .codex/hooks/quality_gate.py MAX_REFUSALS

BLOCK, RELEASE_UNCHANGED, RELEASE_CAPPED = "block", "release_unchanged", "release_capped"


def session_key(session):
    """The 16-hex-digit key naming one session's refusal marker files, or None without a session.

    Pure: sha256 of the session id, so the id never appears in a file name. None (no session id, or
    not a string) keeps the legacy un-keyed marker names."""
    if not isinstance(session, str) or not session:
        return None
    import hashlib
    return hashlib.sha256(session.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def valid_session_key(key):
    """True only for a key as session_key makes it: exactly 16 lowercase hex characters.

    Pure. Every consumer checks it before using a key in a file name; anything else means no key."""
    return (isinstance(key, str) and len(key) == 16 and key.isascii()
            and all(c in "0123456789abcdef" for c in key))


def gate_refusal(previous, continued, is_contract, same_as_last):
    """Decide one refused Stop. Returns (action, marker).

    previous: counter text from the failed marker ('' if none, optionally prefixed 'c').
    continued: the Stop continues an earlier refusal (a fresh Stop restarts the count at 1).
    is_contract: the refusal is about the contract, not the code.
    same_as_last: session, shipping state, reason and contract equal the last recorded refusal;
        only meaningful for a non-contract refusal (callers pass False otherwise).
    The marker is what the caller stores: 'c' prefix for contract refusals, then the count.

    Models a hook Stop only. Known v4 differences it does not reproduce: the shell strips one leading
    'c' from the stored marker while Codex (and this function) strip all; Codex falls back to count 1
    (or MAX+1 on a continued Stop) when the runtime directory is unwritable; the shell also drops the
    pass cache on a non-contract refusal and needs a readable gate state for the unchanged check.
    """
    raw = previous.strip().lstrip("c") if continued else ""
    count = (int(raw) if raw.isascii() and raw.isdigit() else 0) + 1
    marker = f"{'c' if is_contract else ''}{count}"
    if not is_contract and same_as_last:
        return RELEASE_UNCHANGED, marker
    if count > MAX_REFUSALS:
        return RELEASE_CAPPED, marker
    return BLOCK, marker
