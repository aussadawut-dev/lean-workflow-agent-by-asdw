"""Task progress: one runtime state file rendered as a solid/shade bar on every surface.

The percentage follows the lean-task phases; inside a phase, optional done/total counts
(tasks, tests, checks) refine it. The state is local and ignored; it is never evidence.
"""
import json
import time

from .util import LeanError, read_json, runtime, safe_path, write_json

PHASES = ("contract", "scope", "implement", "test", "validate", "review", "gate")
DONE = "done"
FILLED, EMPTY = "█", "░"
WIDTH = 20
STATE = "progress.json"


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


def load(root):
    """The current state, or None when no task is tracked or the file is unreadable."""
    try:
        state = read_json(path(root))
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or state.get("phase") not in PHASES + (DONE,):
        return None
    return state


def update(root, phase, done=None, total=None, task=None, note=None):
    if phase not in PHASES + (DONE,):
        raise LeanError(f"unknown phase {phase!r}; use one of: {', '.join(PHASES + (DONE,))}")
    if (done is None) != (total is None):
        raise LeanError("--done and --total go together")
    if total is not None and (total < 1 or done < 0 or done > total):
        raise LeanError("counts must satisfy 0 <= done <= total and total >= 1")
    previous = load(root) or {}
    state = {"phase": phase, "task": task if task is not None else previous.get("task", ""),
             "done": done, "total": total, "note": note or "", "updated": time.time()}
    runtime(root)
    write_json(path(root), state)
    from . import activity
    activity.record(root, "phase", phase=phase, task=state["task"], done=done, total=total, note=note)
    return state


def clear(root):
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
    state = load(root)
    lines = [line(state) if state else render(0.0) + " no task tracked (lean progress set <phase>)"]
    rows = agents(root)
    if rows:
        lines.append("agents:")
        lines += ["  " + agent_line(row) for row in rows]
    return "\n".join(lines)


def to_json(state):
    return json.dumps(state, indent=2) if state else "{}"
