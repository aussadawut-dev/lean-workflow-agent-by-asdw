"""Task progress: one runtime state file rendered as a solid/shade bar on every surface.

The percentage follows the lean-task phases; inside a phase, optional done/total counts
(tasks, tests, checks) refine it. The state is local and ignored; it is never evidence.

Each session keeps its own state in progress/<session>.json (the session comes from
LEAN_SESSION_ID, CLAUDE_CODE_SESSION_ID or CODEX_THREAD_ID), and progress.json holds the latest
update of any session. A surface that knows its session shows that session's state, and another
session's only with a `session <id>:` label, so concurrent sessions in one checkout do not read
each other's bar as their own. Without a session id the shared progress.json is used as before.
"""
import json
import os
import re
import time

from .util import LeanError, read_json, runtime, safe_path, write_json

PHASES = ("contract", "scope", "implement", "test", "validate", "review", "gate")
DONE = "done"
FILLED, EMPTY = "█", "░"
WIDTH = 20
STATE = "progress.json"
SESSIONS = "progress"
SESSION_ENV = ("LEAN_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")
SESSION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
KEEP_SECONDS = 7 * 24 * 3600  # Session files untouched this long are removed on the next update.


def render(fraction, width=WIDTH, percent=True):
    """`████████░░░░░░░░░░░░ 40%`: one solid cell per 1/width, the rest shaded."""
    fraction = min(1.0, max(0.0, fraction))
    filled = int(round(fraction * width))
    text = FILLED * filled + EMPTY * (width - filled)
    return f"{text} {int(fraction * 100 + 1e-9)}%" if percent else text


def fraction(state):
    phase = state.get("phase")
    if phase == DONE:
        return 1.0
    index = PHASES.index(phase)
    done, total = state.get("done"), state.get("total")
    inner = done / total if isinstance(total, int) and total > 0 and isinstance(done, int) else 0.0
    return (index + min(1.0, inner)) / len(PHASES)


def line(state, width=WIDTH):
    """One display line: bar, phase (with counts) and task."""
    parts = [render(fraction(state), width), state["phase"]]
    if isinstance(state.get("total"), int) and state.get("total"):
        parts[-1] += f" {state.get('done', 0)}/{state['total']}"
    if state.get("note"):
        parts.append(f"({state['note']})")
    if state.get("task"):
        parts.append("— " + state["task"])
    return " ".join(parts)


def path(root):
    return safe_path(runtime(root, create=False), STATE)


def valid_session(session):
    return session if isinstance(session, str) and SESSION_NAME.fullmatch(session) and ".." not in session else ""


def env_session():
    """This process's session id from the environment, or "" when none is set."""
    for name in SESSION_ENV:
        found = valid_session(os.environ.get(name, ""))
        if found:
            return found
    return ""


def session_path(root, session):
    return safe_path(runtime(root, create=False), f"{SESSIONS}/{session}.json")


def read(file):
    try:
        state = read_json(file)
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or state.get("phase") not in PHASES + (DONE,):
        return None
    return state


def load(root, session=None, others=True):
    """The state to show, or None when no task is tracked or the file is unreadable.

    `session` None means this process's session (env_session()); "" means the shared latest state.
    A session's own state comes first; otherwise the latest state of any session when `others`.
    """
    session = env_session() if session is None else valid_session(session)
    if session:
        own = read(session_path(root, session))
        if own is not None:
            return own
        if not others:
            return None
    return read(path(root))


def shown(root, session=None, others=True):
    """The display line for `session`: its own state, or another session's with a label; None if none."""
    session = env_session() if session is None else valid_session(session)
    state = load(root, session, others)
    if state is None:
        return None
    owner = state.get("session") if isinstance(state.get("session"), str) else ""
    text = line(state)
    return f"session {owner[:8]}: {text}" if session and owner and owner != session else text


def update(root, phase, done=None, total=None, task=None, note=None, session=None):
    if phase not in PHASES + (DONE,):
        raise LeanError(f"unknown phase {phase!r}; use one of: {', '.join(PHASES + (DONE,))}")
    if (done is None) != (total is None):
        raise LeanError("--done and --total go together")
    if total is not None and (total < 1 or done < 0 or done > total):
        raise LeanError("counts must satisfy 0 <= done <= total and total >= 1")
    session = env_session() if session is None else valid_session(session)
    shared = read(path(root)) or {}
    previous = read(session_path(root, session)) if session else shared
    if previous is None:  # A session's first update keeps an unowned or its own shared task.
        previous = shared if shared.get("session", "") in ("", session) else {}
    state = {"phase": phase, "task": task if task is not None else previous.get("task", ""),
             "done": done, "total": total, "note": note or "", "updated": time.time(), "session": session}
    runtime(root)
    if session:
        folder = safe_path(runtime(root), SESSIONS)
        folder.mkdir(exist_ok=True)
        prune(folder, state["updated"])
        write_json(session_path(root, session), state)
    write_json(path(root), state)
    from . import activity
    activity.record(root, "phase", phase=phase, task=state["task"], done=done, total=total, note=note)
    return state


def prune(folder, now):
    for file in folder.glob("*.json"):
        try:
            if not file.is_symlink() and now - file.stat().st_mtime > KEEP_SECONDS:
                file.unlink()
        except OSError:
            pass


def clear(root, session=None):
    """Forget `session`'s progress, and the shared latest state when it is that session's or unowned."""
    session = env_session() if session is None else valid_session(session)
    if session:
        session_path(root, session).unlink(missing_ok=True)
    latest = read(path(root))
    if latest is None or not session or latest.get("session", "") in ("", session):
        path(root).unlink(missing_ok=True)


def agents(root):
    """Per-agent rows of the latest `lean spawn run`, from its status file."""
    try:
        status = read_json(safe_path(runtime(root, create=False), "spawn/current.json"))
    except (OSError, ValueError):
        return []
    rows = status.get("agents") if isinstance(status, dict) else None
    return rows if isinstance(rows, list) else []


def agent_line(row, width=WIDTH):
    state = row.get("progress")
    if row.get("status") == "done":
        shown = render(1.0, width)
    elif isinstance(state, dict) and state.get("phase") in PHASES + (DONE,):
        shown = render(fraction(state), width)
    else:
        shown = render(0.0, width)
    return f"{shown} {row.get('id', '?')} [{row.get('provider', '?')}/{row.get('model', '?')}] {row.get('status', '?')}"


def watch_frame(root):
    """The text `lean watch` redraws: task bar first, then one bar per spawned agent."""
    text = shown(root)
    lines = [text or render(0.0) + " no task tracked (lean progress set <phase>)"]
    rows = agents(root)
    if rows:
        lines.append("agents:")
        lines += ["  " + agent_line(row) for row in rows]
    return "\n".join(lines)


def to_json(state):
    return json.dumps(state, indent=2) if state else "{}"
