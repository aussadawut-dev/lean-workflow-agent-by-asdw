"""Development activity log: timed events (phases, gate runs, tests, spawns, reviews, contracts).

Events append to .agent-runtime/activity.jsonl as one JSON object per line. Recording never
interrupts work: a log that cannot be written is skipped. `lean log` shows a timeline and how long
each phase took; `lean log --export` keeps a copy in the repository for later review.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from .util import RUNTIME, write_text

FILE = "activity.jsonl"
MAX_BYTES = 5_000_000  # Rotated to activity.1.jsonl beyond this, so the log never grows without bound.


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value):
    """An aware datetime; a value without a zone is read as UTC, an unreadable one is None."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def path(root):
    return Path(root) / RUNTIME / FILE


def record(root, event, **fields):
    """Append one event; never raise (the log is a convenience, not a gate)."""
    try:
        runtime = Path(root) / RUNTIME
        if runtime.is_symlink():
            return
        runtime.mkdir(exist_ok=True)
        log = runtime / FILE
        if log.is_symlink():
            return
        if log.is_file() and log.stat().st_size > MAX_BYTES:
            log.replace(runtime / "activity.1.jsonl")
        entry = {"at": now(), "event": event}
        entry.update({key: value for key, value in fields.items() if value not in (None, "")})
        with log.open("a") as out:
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (OSError, ValueError, TypeError):
        pass


def load(root, since=None, task=None):
    """Events in order, skipping unreadable lines; optionally only after `since` or for one task."""
    events = []
    for name in ("activity.1.jsonl", FILE):
        try:
            lines = (Path(root) / RUNTIME / name).read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and parse_time(entry.get("at")) is not None:
                events.append(entry)
    if since is not None:
        boundary = parse_time(since)
        events = [entry for entry in events if boundary is None or parse_time(entry["at"]) >= boundary]
    if task:
        events = [entry for entry in events if entry.get("task") == task or entry.get("event") != "phase"]
    return events


def phase_durations(events):
    """{task: [(phase, seconds or None while still open)]} from consecutive phase events of each task."""
    found, last = {}, {}
    for entry in events:
        if entry.get("event") != "phase":
            continue
        task = entry.get("task") or "(no task)"
        when = parse_time(entry["at"])
        if task in last:
            phase, began = last[task]
            found.setdefault(task, []).append((phase, (when - began).total_seconds()))
        if entry.get("phase") == "done":
            found.setdefault(task, []).append(("done", 0.0))
            last.pop(task, None)
        else:
            last[task] = (entry.get("phase"), when)
    for task, (phase, _) in last.items():
        found.setdefault(task, []).append((phase, None))
    return found


def duration(seconds):
    if seconds is None:
        return "open"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def describe(entry):
    kind = entry.get("event")
    if kind == "phase":
        counts = f" {entry['done']}/{entry['total']}" if entry.get("total") else ""
        note = f" ({entry['note']})" if entry.get("note") else ""
        return f"phase {entry.get('phase')}{counts}{note} — {entry.get('task', '')}".rstrip(" —")
    if kind == "gate":
        return (f"gate {entry.get('result')} ({entry.get('checks', 0)} checks, {duration(entry.get('seconds'))})"
                + (f": {entry['reason']}" if entry.get("reason") else ""))
    if kind == "test":
        return (f"tests {entry.get('files', 0)} files, {entry.get('failed', 0)} failed "
                f"({duration(entry.get('seconds'))}): {entry.get('selection', '')}")
    if kind == "spawn":
        return (f"agent {entry.get('id')} [{entry.get('provider')}/{entry.get('model')}] {entry.get('status')} "
                f"({duration(entry.get('seconds'))})")
    if kind == "review":
        return f"review {entry.get('verdict')} by {entry.get('reviewer')}"
    if kind == "contract":
        return f"contract ({entry.get('source')}): {entry.get('contract')}"
    return json.dumps({key: value for key, value in entry.items() if key not in ("at", "event")})


def timeline(events):
    return [f"{entry['at']}  {describe(entry)}" for entry in events]


def summary(events):
    """Per task: phase durations; overall: counts and time of gate runs, tests, agents and reviews."""
    lines = []
    for task, phases in phase_durations(events).items():
        total = sum(seconds for _, seconds in phases if seconds)
        lines.append(f"{task}: {duration(total)} in phases")
        lines += [f"  {phase:<10} {duration(seconds)}" for phase, seconds in phases if phase != "done"]
    gates = [entry for entry in events if entry.get("event") == "gate"]
    if gates:
        results = {}
        for entry in gates:
            results[entry.get("result")] = results.get(entry.get("result"), 0) + 1
        lines.append("gate runs: " + ", ".join(f"{count} {result}" for result, count in sorted(results.items())))
    tests = [entry for entry in events if entry.get("event") == "test"]
    if tests:
        lines.append(f"test runs: {len(tests)} ({sum(entry.get('failed', 0) > 0 for entry in tests)} with failures), "
                     f"{duration(sum(entry.get('seconds', 0) for entry in tests))} total")
    agents = [entry for entry in events if entry.get("event") == "spawn"]
    if agents:
        lines.append(f"agents: {len(agents)} ({sum(entry.get('status') == 'done' for entry in agents)} done), "
                     f"{duration(sum(entry.get('seconds', 0) or 0 for entry in agents))} agent time")
    reviews = [entry for entry in events if entry.get("event") == "review"]
    if reviews:
        lines.append("reviews: " + ", ".join(entry.get("verdict", "?") for entry in reviews))
    return lines or ["no activity recorded"]


def export(root, destination, events):
    """Write the log to a project file: Markdown (.md) or JSON lines otherwise."""
    destination = Path(destination)
    if destination.suffix == ".md":
        text = ("# Lean activity log\n\nExported " + now() + " from `.agent-runtime/activity.jsonl`.\n\n"
                "## Summary\n\n" + "\n".join(f"- {line}" if not line.startswith("  ") else f"  - {line.strip()}"
                                             for line in summary(events))
                + "\n\n## Timeline\n\n" + "\n".join(f"- {line}" for line in timeline(events)) + "\n")
    else:
        text = "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in events)
    write_text(destination, text)
    return destination
