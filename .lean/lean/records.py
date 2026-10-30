"""Workflow modes, trackers and the full mode's local queue leases."""

import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

from .util import WORKFLOW_ROOT, write_text as atomic_write_text

MODES = ("standard", "tracker", "full")
EXECUTIONS = ("direct", "delegated")
CONTRACT_LIFETIMES = ("prompt", "session")  # Matches guard.LIFETIMES; prompt is the default.
TRACKER_STATES = ("PLANNED", "IN_PROGRESS", "VALIDATING", "REVIEWING", "DONE", "BLOCKED", "FAILED")
LEASE_SECONDS = 30 * 60
ID = re.compile(r"Q[0-9]{4,}")
TRACKER = re.compile(r"TCK[0-9]{3,}")
HISTORY = "docs/history/agent-workflow"  # Archived trackers: read-only, IDs stay reserved.
REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}")
TEMPLATE_ROOT = None  # Workflow templates when the record root differs from the workflow root.
CHECKLIST_HEADING = re.compile(r"(?:acceptance criteri(?:a|on)|tasks?)\b", re.IGNORECASE)
CHECKBOX = re.compile(r"[ \t]*(?:[-+*]|[0-9]+[.)])[ \t]+\[([ xX])\][ \t]*(.*)")


def fail(message):
    raise ValueError(message)


def tracker_template(root):
    source = TEMPLATE_ROOT if TEMPLATE_ROOT is not None else root / ".lean/templates"
    if not (source / "tracker.md").is_file():
        source = WORKFLOW_ROOT / ".lean/templates"
    return (source / "tracker.md").read_text()


def validate_project_paths(root):
    """Keep workflow data and its parents in this checkout before any mutation.

    Local CLI locking coordinates cooperating processes; it does not protect
    against another process replacing filesystem paths during an operation.
    """
    for relative in (".lean/config.json", ".gitignore", ".agent-runtime/queue.lock",
                     ".agent-runtime/claims", "docs/tracking", HISTORY, ".agents/queue"):
        path = root
        for part in Path(relative).parts:
            path = path / part
            if path.is_symlink():
                fail(f"workflow path must not be a symlink: {path}")
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_symlink():
                    fail(f"workflow path must not be a symlink: {child}")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as out:
        json.dump(value, out, indent=2)
        out.write("\n")
        temporary = Path(out.name)
    os.replace(temporary, path)


def write_text(path, value):
    atomic_write_text(path, value)


def read_json(path):
    with path.open() as source:
        return json.load(source)


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str):
        fail("timestamp must be an ISO 8601 string with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail("invalid ISO 8601 timestamp")
    if parsed.tzinfo is None:
        fail("timestamp requires a timezone")
    return parsed.timestamp()


def config(root):
    path = root / ".lean/config.json"
    value = read_json(path) if path.exists() else {"mode": "standard", "configured": False}
    if not isinstance(value, dict) or value.get("mode") not in MODES or not isinstance(value.get("configured"), bool):
        fail(f"invalid workflow config: {path}")
    if not value["configured"] and value["mode"] != "standard":
        fail("unconfigured workflow must use standard mode")
    value.setdefault("execution", "direct")
    if value["execution"] not in EXECUTIONS:
        fail("execution must be direct or delegated")
    if value.get("contract_lifetime", "prompt") not in CONTRACT_LIFETIMES:
        fail("contract_lifetime must be prompt or session")
    return value


def mode_at_least(root, minimum):
    mode = config(root)["mode"]
    if MODES.index(mode) < MODES.index(minimum):
        fail(f"{minimum} mode required; current mode is {mode}")


def configure(root, mode, execution=None, **options):
    with locked(root):
        configure_locked(root, mode, execution, **options)


def configure_locked(root, mode, execution=None, **options):
    current = config(root)
    if MODES.index(mode) < MODES.index(current["mode"]):
        fail("mode downgrade is not automatic; resolve existing tracking and claims first")
    if mode in ("tracker", "full"):
        tracking = root / "docs/tracking"
        tracking.mkdir(parents=True, exist_ok=True)
        template = tracking / "TEMPLATE.md"
        if not template.exists():
            template.write_text(tracker_template(root))
        readme = tracking / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Tracking\n\nCreate one TCKNNN.md or TCKNNN-slug.md document from TEMPLATE.md for each non-trivial workset. "
                "Record the goal, acceptance criteria, decisions, task status, validation evidence, "
                "and next step. Keep the tracker current before reporting DONE.\n"
            )
    if mode == "full":
        queue = root / ".agents/queue/items"
        queue.mkdir(parents=True, exist_ok=True)
        (queue / ".gitkeep").touch(exist_ok=True)
        guide = root / ".agents/queue/README.md"
        if not guide.exists():
            guide.write_text(
                "# Queue\n\nCreate QNNNN.json items in items/ using "
                "`.lean/templates/queue-item.json`. Every item must name an existing TCK tracker, "
                "dependencies, and exclusive scopes. Use `python3 .lean/bin/lean queue claim --id QNNNN --agent NAME --request-id UUID`, "
                "heartbeat, complete, or release to manage leases. Never edit runtime claims by hand.\n"
            )
    if mode in ("tracker", "full"):
        ignore = root / ".gitignore"
        lines = ignore.read_text().splitlines() if ignore.exists() else []
        if ".agent-runtime/" not in lines:
            with ignore.open("a") as out:
                if lines:
                    out.write("\n")
                out.write("# Local workflow leases\n.agent-runtime/\n")
    if MODES.index(mode) > MODES.index(current["mode"]):
        validate_records(root, mode)
    current.update(mode=mode, configured=True, execution=execution or current["execution"])
    current.update({key: value for key, value in options.items() if value is not None})
    write_json(root / ".lean/config.json", current)
    print(f"mode: {mode}")


def tracker_matches(directory, tracker_id, recursive=False, suffix=".md"):
    """Files in a directory whose name carries this exact ID; suffix="" matches any history file."""
    if not directory.is_dir():
        return []
    pattern = f"{tracker_id}*{suffix}"
    found = directory.rglob(pattern) if recursive else directory.glob(pattern)
    return [p for p in found if p.is_file() and (p.stem == tracker_id or p.stem.startswith(tracker_id + "-"))]


def reserved_by_history(root, tracker_id):
    """Any archived file named for this ID keeps the ID reserved."""
    return bool(tracker_matches(root / HISTORY, tracker_id, recursive=True, suffix=""))


def tracker_file(root, tracker_id, archived=False):
    """Resolve an active tracker; archived=True also resolves read-only history for linkage."""
    if not TRACKER.fullmatch(tracker_id):
        fail("invalid tracker id")
    matches = tracker_matches(root / "docs/tracking", tracker_id)
    history = tracker_matches(root / HISTORY, tracker_id, recursive=True)
    if not matches and history and not archived:
        fail(f"tracker is archived and read-only: {tracker_id}")
    if archived:
        matches += history
    if len(matches) != 1:
        fail(f"expected one tracker document for {tracker_id}, found {len(matches)}")
    return matches[0]


def tracker_document_counts(root, requested):
    """Count requested active/history tracker IDs for one queue validation."""
    counts = {}
    for directory, recursive in ((root / "docs/tracking", False), (root / HISTORY, True)):
        if not directory.is_dir():
            continue
        documents = directory.rglob("*.md") if recursive else directory.glob("*.md")
        for path in documents:
            tracker_id = path.stem.split("-", 1)[0]
            if tracker_id in requested and path.is_file():
                counts[tracker_id] = counts.get(tracker_id, 0) + 1
    return counts


def unchecked_tracker_items(content):
    """Return unchecked items under Acceptance criteria/Tasks headings and their subheadings.

    Every list checkbox counts, whatever its label or the heading level, so an
    unconventional format cannot hide open work. Legacy trackers without these
    sections remain valid.
    """
    unchecked, level, fenced = [], None, False
    for line in content.splitlines():
        if re.match(r"[ \t]*(```|~~~)", line):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = re.fullmatch(r"(#{1,6})[ \t]+(.*?)[ \t#]*", line)
        if heading:
            depth = len(heading.group(1))
            if level is not None and depth <= level:
                level = None
            if level is None and CHECKLIST_HEADING.match(heading.group(2)):
                level = depth
            continue
        entry = CHECKBOX.fullmatch(line)
        if level is not None and entry and entry.group(1) == " ":
            unchecked.append(entry.group(2).split(":", 1)[0].strip())
    return unchecked


def status_problem(name, content):
    """Why a tracker's Status line is invalid, naming file:line, or None when it is one valid line."""
    found = [(number, line) for number, line in enumerate(content.splitlines(), 1)
             if line.startswith("Status:") and not line.startswith("Status note:")]
    valid = [line for _, line in found if re.fullmatch(r"Status: ([A-Z_]+)", line)
             and line[len("Status: "):] in TRACKER_STATES]
    if len(found) == 1 and len(valid) == 1:
        return None
    convention = (f"a tracker needs exactly one `Status: <STATE>` line ({', '.join(TRACKER_STATES)}); "
                  "put notes on a separate `Status note:` line")
    if not found:
        return f"invalid tracker status: {name}: no Status line; {convention}"
    return "invalid tracker status: " + "; ".join(f"{name}:{number}: {line!r}" for number, line in found) + \
        f"; {convention}"


def single_line(value, name):
    """Reject line breaks that would forge Status or Evidence lines in a tracker."""
    if "".join(value.splitlines()) != value:
        fail(f"{name} must be a single line")
    return value.strip()


def tracker_command(root, args):
    with locked(root):
        mode_at_least(root, "tracker")
        if args.action == "new":
            title = single_line(args.title, "tracker title")
            if not TRACKER.fullmatch(args.id) or not title:
                fail("valid tracker id and title are required")
            directory = root / "docs/tracking"
            matches = list(directory.glob(f"{args.id}*.md"))
            if any(p.stem == args.id or p.stem.startswith(args.id + "-") for p in matches):
                fail(f"tracker already exists: {args.id}")
            if reserved_by_history(root, args.id):
                fail(f"tracker id reserved by history: {args.id}")
            content = tracker_template(root)
            content = content.replace("TCKNNN — Title", f"{args.id} — {title}", 1)
            path = directory / f"{args.id}.md"
            with path.open("x") as out:
                out.write(content)
            print(f"created: {path.relative_to(root)}")
        elif args.action == "status":
            path = tracker_file(root, args.id)
            evidence = single_line(args.evidence, "evidence")
            content = path.read_text()
            matches = list(re.finditer(r"(?m)^Status: [A-Z_]+$", content))
            if len(matches) != 1:
                fail(status_problem(path.name, content) or f"expected one Status line: {args.id}")
            if args.status == "DONE" and not evidence:
                fail("DONE requires evidence")
            if args.status == "DONE" and unchecked_tracker_items(content):
                fail(f"DONE requires all acceptance criteria and tasks checked: {args.id}")
            if args.status == "DONE" and config(root)["mode"] == "full":
                linked = [item for item in items(root).values() if item["tracker"] == args.id]
                if not linked or any(item["status"] != "DONE" for item in linked):
                    fail("all linked queue items must be DONE before the tracker")
            if args.status == "DONE":
                from . import gate, progress
                gate.check_closure(getattr(args, "evidence_root", root), root,
                                   getattr(args, "contract", None), progress.env_session())
            content = content[:matches[0].start()] + f"Status: {args.status}" + content[matches[0].end():]
            if evidence:
                marker = "## Evidence\n"
                if marker not in content:
                    fail(f"missing Evidence section: {args.id}")
                content = content.replace(marker, marker + f"\n- {evidence}\n", 1)
            write_text(path, content)
            print(f"tracker {args.id}: {args.status}")
        elif args.action == "archive":
            archive_trackers(root, args)


def archive_trackers(root, args):
    """Move valid DONE trackers to history; every check runs before the first move."""
    mode = config(root)["mode"]
    # Refuse invalid records instead of hiding them from check in history.
    validate_records(root, mode)
    directory, history = root / "docs/tracking", root / HISTORY
    if args.id:
        if not TRACKER.fullmatch(args.id):
            fail("invalid tracker id")
        targets = tracker_matches(directory, args.id)
        if not targets:
            if tracker_matches(history, args.id, recursive=True):
                fail(f"tracker is already archived: {args.id}")
            fail(f"expected one tracker document for {args.id}, found 0")
    else:
        targets = sorted(directory.glob("TCK*.md"))
    selected = []
    for path in targets:
        tracker_id = path.stem.split("-", 1)[0]
        status = re.findall(r"(?m)^Status: ([A-Z_]+)$", path.read_text())[0]
        if status != "DONE":
            if args.id:
                fail(f"only DONE trackers can be archived: {tracker_id} is {status}")
            continue
        # Only an archived tracker document collides; takeover keeps a migrated tracker's
        # original as a .txt beside the still-active tracker.
        if tracker_matches(history, tracker_id, recursive=True) or (history / path.name).exists():
            fail(f"tracker id already archived: {tracker_id}")
        selected.append((tracker_id, path))
    report = {"selected": [tid for tid, _ in selected], "archived": [], "applied": args.apply}
    if args.apply and selected:
        try:
            history.mkdir(parents=True, exist_ok=True)
            for tracker_id, path in selected:
                os.replace(path, history / path.name)
                report["archived"].append(tracker_id)
        except OSError as error:
            print(json.dumps(report, indent=2))
            fail(f"archive stopped after {len(report['archived'])} of {len(selected)} trackers: {error}")
    print(json.dumps(report, indent=2))


def queue_history(root):
    """Read immutable DONE snapshots; never expire records or rewrite history."""
    result = {}
    for path in sorted((root / ".agents/queue/history").glob("*.json")):
        record = read_json(path)
        if (not ID.fullmatch(path.stem) or not isinstance(record, dict)
                or record.get("version") != 1 or record.get("reason") not in ("old", "all")
                or not isinstance(record.get("content"), str)
                or not isinstance(record.get("sha256"), str)):
            fail(f"invalid queue history: {path}")
        timestamp(record.get("archived_at"))
        if hashlib.sha256(record["content"].encode("utf-8")).hexdigest() != record["sha256"]:
            fail(f"queue history checksum mismatch: {path.stem}")
        item = json.loads(record["content"])
        if not isinstance(item, dict) or item.get("id") != path.stem or item.get("status") != "DONE":
            fail(f"queue history must retain its original DONE id: {path.stem}")
        result[path.stem] = record
    return result


def items(root):
    directory = root / ".agents/queue/items"
    history = queue_history(root)
    retired = set()
    for path in sorted((root / ".agents/queue/retired").glob("*.txt")):
        original = read_json(path)
        if (not ID.fullmatch(path.stem) or not isinstance(original, dict)
                or original.get("id") != path.stem or original.get("status") != "CANCELLED"):
            fail(f"invalid cancellation history: {path}")
        retired.add(path.stem)
    if retired & set(history):
        fail("cancelled queue id reused in DONE history")
    sources = [(root / ".agents/queue/history" / (key + ".json"), json.loads(record["content"]))
               for key, record in history.items()]
    for path in sorted(directory.glob("*.json")):
        value = read_json(path)
        if path.stem in retired:
            fail(f"cancelled queue id reused: {path.stem}")
        if path.stem in history:
            # A published archive is authoritative after an interrupted unlink.
            # A different source with the same id is reuse/corruption, not recovery.
            if path.read_bytes() != history[path.stem]["content"].encode("utf-8"):
                fail(f"archived queue id reused or modified: {path.stem}")
            continue
        sources.append((path, value))
    result = {}
    tracker_counts = None
    for path, value in sources:
        item_id = value.get("id") if isinstance(value, dict) else None
        if not isinstance(item_id, str) or not ID.fullmatch(item_id) or path.name != f"{item_id}.json":
            fail(f"invalid queue item id: {path}")
        if item_id in result:
            fail(f"duplicate queue item: {item_id}")
        if value.get("status") not in ("READY", "DONE", "BLOCKED"):
            fail(f"invalid status: {item_id}")
        if not isinstance(value.get("title"), str) or not value["title"].strip():
            fail(f"missing title: {item_id}")
        if not isinstance(value.get("tracker"), str) or not TRACKER.fullmatch(value["tracker"]):
            fail(f"invalid tracker: {item_id}")
        if tracker_counts is None:
            # Collect without validating later items: the first error must still
            # follow source order, including archived queue records.
            requested = {record["tracker"] for _, record in sources
                         if isinstance(record, dict) and isinstance(record.get("tracker"), str)
                         and TRACKER.fullmatch(record["tracker"])}
            tracker_counts = tracker_document_counts(root, requested)
        count = tracker_counts.get(value["tracker"], 0)
        if count != 1:
            fail(f"expected one tracker document for {value['tracker']}, found {count}")
        for field in ("created_at", "completed_at"):
            if field in value:
                timestamp(value[field])
        for field in ("dependencies", "scopes"):
            if not isinstance(value.get(field), list) or not all(isinstance(x, str) for x in value[field]):
                fail(f"invalid {field}: {item_id}")
        if not value["scopes"] or len(set(value["scopes"])) != len(value["scopes"]):
            fail(f"missing or repeated scope: {item_id}")
        for scope in value["scopes"]:
            scope_key(scope)
        if value["status"] == "DONE" and (not isinstance(value.get("evidence"), str) or not value["evidence"].strip()):
            fail(f"DONE without evidence: {item_id}")
        result[item_id] = value
    for item_id, value in result.items():
        for dep in value["dependencies"]:
            if dep not in result or dep == item_id:
                fail(f"invalid dependency {dep}: {item_id}")
    visiting, visited = set(), set()

    def visit(item_id):
        if item_id in visiting:
            fail(f"dependency cycle: {item_id}")
        if item_id in visited:
            return
        visiting.add(item_id)
        for dep in result[item_id]["dependencies"]:
            visit(dep)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in result:
        visit(item_id)
    for item_id, item in result.items():
        if item["status"] == "DONE" and any(result[dependency]["status"] != "DONE" for dependency in item["dependencies"]):
            fail(f"DONE item has unfinished dependencies: {item_id}")
    return result


def validate_records(root, mode, include_retained=False):
    """Read-only validation; callers hold the workflow lock when applying changes."""
    from . import intake
    intake.validate(intake.load(root))
    tracker_statuses, all_items, claims = {}, {}, {}
    if mode in ("tracker", "full") or include_retained:
        if ".agent-runtime/" not in (root / ".gitignore").read_text().splitlines():
            fail("runtime leases are not ignored by git")
        for path in (root / "docs/tracking/TEMPLATE.md", root / "docs/tracking/README.md"):
            if not path.is_file():
                fail(f"missing tracking file: {path}")
        for path in (root / "docs/tracking").glob("TCK*.md"):
            if not re.fullmatch(r"TCK[0-9]{3,}(?:-[a-zA-Z0-9_-]+)?", path.stem):
                fail(f"invalid tracker filename: {path}")
            statuses = re.findall(r"(?m)^Status: ([A-Z_]+)$", path.read_text())
            if len(statuses) != 1 or statuses[0] not in TRACKER_STATES:
                fail(status_problem(path.relative_to(root), path.read_text()) or f"invalid tracker status: {path}")
            tracker_id = path.stem.split("-", 1)[0]
            if tracker_id in tracker_statuses:
                fail(f"duplicate tracker id: {tracker_id}")
            tracker_statuses[tracker_id] = statuses[0]
            if statuses[0] == "DONE":
                content = path.read_text()
                evidence = content.split("## Evidence\n", 1)[-1].split("\n## ", 1)[0]
                if "## Evidence\n" not in content or not re.search(r"(?m)^- \S", evidence):
                    fail(f"DONE tracker without evidence: {path}")
                if unchecked_tracker_items(content):
                    fail(f"DONE tracker has unchecked acceptance criteria or tasks: {path}")
    if mode == "full" or include_retained:
        if mode == "full" and not (root / ".agents/queue/items").is_dir():
            fail("missing queue items directory")
        if mode == "full" and not (root / ".agents/queue/README.md").is_file():
            fail("missing queue guide")
        all_items = items(root)
        claims = active_claims(root, cleanup=False)
        validate_claims(all_items, claims)
        for tracker_id, status in tracker_statuses.items():
            if mode == "full" and status == "DONE":
                linked = [item for item in all_items.values() if item["tracker"] == tracker_id]
                if not linked or any(item["status"] != "DONE" for item in linked):
                    fail(f"DONE tracker has unfinished queue items: {tracker_id}")
    return tracker_statuses, all_items, claims


def check(root):
    with locked(root, read_only=True):
        current = config(root)
        validate_records(root, current["mode"])
    print(f"workflow ok: {current['mode']}")


def downgrade(root, target, apply=False, keep_pending=False):
    with locked(root, read_only=not apply):
        current = config(root)
        if MODES.index(target) >= MODES.index(current["mode"]):
            fail("downgrade target must be lower than the current mode")
        trackers, queue, claims = validate_records(root, current["mode"], include_retained=True)
        pending_queue = sorted(key for key, item in queue.items() if item["status"] != "DONE")
        pending_trackers = sorted(key for key, state in trackers.items() if state != "DONE")
        running = sorted(key for key, state in trackers.items()
                         if state in ("IN_PROGRESS", "VALIDATING", "REVIEWING"))
        blockers = []
        if claims:
            blockers.append("active claims must be released or completed: " + ", ".join(sorted(claims)))
        if target == "standard" and running:
            blockers.append("active trackers must be resolved: " + ", ".join(running))
        if (pending_queue or (target == "standard" and pending_trackers)) and not keep_pending:
            blockers.append("use --keep-pending to acknowledge preserved, paused work")
        report = {"from": current["mode"], "to": target, "execution": current["execution"],
                  "trackers": len(trackers), "queue_items": len(queue),
                  "pending_queue": pending_queue, "pending_trackers": pending_trackers,
                  "active_claims": sorted(claims),
                  "expired_claims": sorted(path.stem for path in
                      (root / ".agent-runtime/claims").glob("*.json") if path.stem not in claims),
                  "blockers": blockers, "applied": False}
        if apply and not blockers:
            current.update(mode=target, configured=True)
            write_json(root / ".lean/config.json", current)
            report["applied"] = True
        print(json.dumps(report, indent=2))
        return 2 if blockers else 0


@contextlib.contextmanager
def locked(root, read_only=False):
    validate_project_paths(root)
    runtime = root / ".agent-runtime"
    path = runtime / "queue.lock"
    if read_only and not path.exists():
        # Preview is advisory; apply always acquires the lock and rechecks.
        yield
        return
    if not read_only:
        runtime.mkdir(exist_ok=True)
    with path.open("r" if read_only else "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def validate_claim(path, claim):
    expiry = claim.get("expires_at") if isinstance(claim, dict) else None
    try:
        valid_expiry = type(expiry) in (int, float) and math.isfinite(expiry)
    except OverflowError:
        valid_expiry = False
    if (not isinstance(claim, dict) or not ID.fullmatch(path.stem)
            or claim.get("id") != path.stem
            or not isinstance(claim.get("agent"), str) or not claim["agent"].strip()
            or not isinstance(claim.get("token"), str) or not claim["token"].strip()
            or not isinstance(claim.get("request_id"), str)
            or not REQUEST_ID.fullmatch(claim["request_id"])
            or not valid_expiry):
        fail(f"invalid claim file: {path}")


def active_claims(root, cleanup=True):
    directory = root / ".agent-runtime/claims"
    if cleanup:
        directory.mkdir(parents=True, exist_ok=True)
    active = {}
    for path in directory.glob("*.json"):
        claim = read_json(path)
        validate_claim(path, claim)
        if claim.get("expires_at", 0) <= time.time():
            if cleanup:
                path.unlink()
        else:
            active[path.stem] = claim
    return active


def scope_key(scope):
    """Lexical scope identity; colon labels are opaque, paths are relative.

    Both slash styles are path separators, independently of the host OS. Never
    resolve files, symlinks or case: scopes also describe files not created yet.
    """
    path = scope.replace("\\", "/")
    if (not scope.strip() or "\x00" in scope or path.startswith("/")
            or re.match(r"^[A-Za-z]:/", path)):
        fail(f"invalid path scope: {scope!r}")
    if ":" in scope:
        return "label", scope
    if any(char in scope for char in "*?[]"):
        fail(f"invalid path scope: {scope!r}")
    parts = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                fail(f"invalid path scope: {scope!r}")
            parts.pop()
        else:
            parts.append(part)
    return "path", tuple(parts)


def overlapping_scope(occupied, candidates):
    """Return a candidate sharing a label or a path ancestor with occupied."""
    keys = [scope_key(scope) for scope in sorted(occupied)]
    for scope in sorted(candidates):
        kind, key = scope_key(scope)
        for held_kind, held in keys:
            if kind != held_kind:
                continue
            if kind == "label":
                if key == held:
                    return scope
            else:
                common = min(len(key), len(held))
                if key[:common] == held[:common]:
                    return scope
    return None


def validate_claims(all_items, claims):
    agents, scopes = set(), set()
    for item_id, claim in claims.items():
        item = all_items.get(item_id)
        if item is None or item["status"] != "READY":
            fail(f"claim has no READY item: {item_id}")
        # Surrounding whitespace must not make one agent look like two.
        if claim["agent"].strip() in agents:
            fail(f"agent owns multiple claims: {claim['agent'].strip()}")
        agents.add(claim["agent"].strip())
        overlap = overlapping_scope(scopes, item["scopes"])
        if overlap is not None:
            fail(f"overlapping active claim scope: {overlap}")
        scopes.update(item["scopes"])
    return scopes


def owned_claim(root, item_id, token):
    if not ID.fullmatch(item_id):
        fail("invalid queue id")
    path = root / ".agent-runtime/claims" / f"{item_id}.json"
    if not path.exists():
        fail(f"no active claim for {item_id}")
    claim = read_json(path)
    validate_claim(path, claim)
    if claim["token"] != token or claim["expires_at"] <= time.time():
        fail(f"invalid or expired claim for {item_id}")
    return path, claim


def queue_command(root, args):
    with locked(root, read_only=args.action == "history"):
        if args.action == "history":
            items(root)  # Validate original data, dependencies and IDs as well as metadata.
            history = queue_history(root)
            if args.id:
                if args.id not in history:
                    fail(f"no archived queue item: {args.id}")
                print(json.dumps(history[args.id], indent=2))
            else:
                print(json.dumps({key: {"title": json.loads(value["content"])["title"],
                                        "archived_at": value["archived_at"], "reason": value["reason"]}
                                  for key, value in history.items()}, indent=2))
            return
        mode_at_least(root, "full")
        if args.action in ("heartbeat", "release", "complete"):
            path, claim = owned_claim(root, args.id, args.token)
            if args.action == "release":
                path.unlink()
                print(f"released: {args.id}")
                return
            item_path = root / ".agents/queue/items" / f"{args.id}.json"
            item = read_json(item_path)
            if not isinstance(item, dict) or item.get("id") != args.id:
                fail(f"invalid queue item: {args.id}")
            if args.action == "heartbeat":
                if item.get("status") != "READY":
                    fail("only READY items can be renewed")
                claim["expires_at"] = time.time() + LEASE_SECONDS
                write_json(path, claim)
                print(f"renewed: {args.id}")
                return
            if not args.evidence.strip():
                fail("completion evidence is required")
            if item.get("status") == "DONE":
                if item.get("evidence") != args.evidence:
                    fail("retry evidence does not match completed item")
                path.unlink()
                print(f"completed: {args.id} (lease cleanup)")
                return
            if item.get("status") != "READY":
                fail("only READY items can be completed")
            # Dependencies may have changed after the lease was granted. Refusal
            # must leave both the READY item and its lease intact for recovery.
            all_items = items(root)
            if any(all_items[dependency]["status"] != "DONE" for dependency in item["dependencies"]):
                fail(f"unfinished dependencies: {args.id}")
            item["status"] = "DONE"
            item["evidence"] = args.evidence
            item["completed_at"] = utc_now()
            write_json(item_path, item)
            path.unlink()
            print(f"completed: {args.id}")
            return

        all_items = items(root)
        archived_ids = set(queue_history(root))
        claims = active_claims(root)
        if args.action == "list":
            validate_claims(all_items, claims)
            for item_id, item in all_items.items():
                if item_id in archived_ids:
                    continue
                owner = claims.get(item_id, {}).get("agent", "-")
                print(f"{item_id} {item['status']} {owner} {item['tracker']} {item['title']}")
            return
        if args.action in ("claim-next", "claim"):
            if not args.agent.strip() or args.agent != args.agent.strip():
                fail("agent id is required and must not have surrounding whitespace")
            if not REQUEST_ID.fullmatch(args.request_id):
                fail("request id must be a stable random identifier of at least eight characters")
            occupied = validate_claims(all_items, claims)
            existing = [(item_id, claim) for item_id, claim in claims.items() if claim["agent"] == args.agent]
            if existing and len(existing) == 1 and existing[0][1]["request_id"] == args.request_id:
                if args.action == "claim-next" or args.id == existing[0][0]:
                    print(json.dumps(existing[0][1]))
                    return
            if existing:
                fail(f"agent already owns an active claim: {args.agent}")
            if args.action == "claim":
                candidates = [(args.id, all_items[args.id])] if args.id in all_items else []
            else:
                candidates = list(all_items.items())
            for item_id, item in candidates:
                if item["status"] != "READY" or item_id in claims:
                    continue
                if any(all_items[dep]["status"] != "DONE" for dep in item["dependencies"]):
                    continue
                if overlapping_scope(occupied, item["scopes"]) is not None:
                    continue
                claim = {"id": item_id, "agent": args.agent, "request_id": args.request_id,
                         "token": uuid.uuid4().hex,
                         "expires_at": time.time() + LEASE_SECONDS}
                write_json(root / ".agent-runtime/claims" / f"{item_id}.json", claim)
                print(json.dumps(claim))
                return
            fail("no claimable queue item")


def context_command(root, args):
    with locked(root, read_only=True):
        cfg = config(root)
        report = {
            "mode": cfg["mode"],
            "configured": cfg["configured"],
            "execution": cfg["execution"],
            "active_tracker": None,
            "git": None,
            "active_claims": [],
            "gate": None,
        }
        tracking_dir = root / "docs/tracking"
        if tracking_dir.is_dir():
            trackers_found = []
            for path in sorted(tracking_dir.glob("TCK*.md")):
                if not re.fullmatch(r"TCK[0-9]{3,}(?:-[a-zA-Z0-9_-]+)?", path.stem):
                    continue
                content = path.read_text()
                statuses = re.findall(r"(?m)^Status: ([A-Z_]+)$", content)
                if len(statuses) != 1:
                    continue
                status = statuses[0]
                tracker_id = path.stem.split("-", 1)[0]
                title_match = re.search(r"^#\s+(?:TCK[0-9]{3,}\s+[—–-]\s+)?(.*)$", content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else path.stem
                next_step_match = re.search(r"## Next step\s*\n+([^\n#]+)", content)
                next_step = next_step_match.group(1).strip() if next_step_match else None
                unchecked = unchecked_tracker_items(content)
                trackers_found.append({
                    "id": tracker_id,
                    "filename": path.name,
                    "title": title,
                    "status": status,
                    "next_step": next_step,
                    "unchecked_tasks": unchecked,
                })
            priority = {"IN_PROGRESS": 1, "VALIDATING": 2, "REVIEWING": 3, "PLANNED": 4}
            active = [t for t in trackers_found if t["status"] in priority]
            if active:
                active.sort(key=lambda t: priority.get(t["status"], 99))
                report["active_tracker"] = active[0]
            report["tracker_counts"] = {
                state.lower(): sum(1 for t in trackers_found if t["status"] == state)
                for state in TRACKER_STATES
            }
        claims = active_claims(root, cleanup=False)
        report["active_claims"] = [
            {"id": cid, "agent": claim.get("agent"), "expires_in": max(0, int(claim.get("expires_at", 0) - time.time()))}
            for cid, claim in claims.items()
        ]
        try:
            check_git = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True, check=False,
            )
            if check_git.returncode == 0:
                branch = subprocess.run(
                    ["git", "-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"],
                    capture_output=True, text=True, check=False,
                ).stdout.strip() or "detached"
                status_proc = subprocess.run(
                    # --no-optional-locks: status must not refresh and rewrite the index.
                    ["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain"],
                    capture_output=True, text=True, check=False,
                )
                status_out = status_proc.stdout.splitlines()
                modified = [line[3:].strip() for line in status_out if line[:2].strip() != "??"]
                untracked = [line[3:].strip() for line in status_out if line.startswith("??")]
                report["git"] = {
                    "branch": branch,
                    "status": "modified" if status_out else "clean",
                    "modified": modified[:20],
                    "untracked": untracked[:20],
                }
        except OSError:
            pass  # No Git available: report git as null.
        from .gate import status as gate_status
        from .progress import load as progress_state
        evidence_root = getattr(args, "evidence_root", root)
        report["evidence_root"] = str(evidence_root)
        report["record_root"] = str(root)
        report["gate"] = {"status": gate_status(evidence_root),
                          "source": "shared gate results in workflow_root; legacy cache/hook markers when no result exists"}
        report["progress"] = progress_state(evidence_root)
        print(json.dumps(report, indent=2))


def parser_for(commands):
    """Add the mode, tracker and queue command groups to a `lean` subparser set."""
    mode = commands.add_parser("mode", help="workflow mode and execution routing")
    mode_actions = mode.add_subparsers(dest="action", required=True)
    setup = mode_actions.add_parser("configure", help="select standard, tracker or full")
    setup.add_argument("mode", choices=MODES)
    setup.add_argument("--execution", choices=EXECUTIONS)
    setup.add_argument("--contract-lifetime", choices=CONTRACT_LIFETIMES,
                       help="prompt (default): a new person's prompt clears the contract; session: it is kept")
    lower = mode_actions.add_parser("downgrade", help="move to a lower mode, preserving records")
    lower.add_argument("mode", choices=MODES)
    choice = lower.add_mutually_exclusive_group(required=True)
    choice.add_argument("--dry-run", action="store_true")
    choice.add_argument("--apply", action="store_true")
    lower.add_argument("--keep-pending", action="store_true")
    mode_actions.add_parser("show", help="print mode and execution as JSON")
    mode_actions.add_parser("check", help="validate the mode and its records")
    mode_actions.add_parser("context", help="read-only summary for resuming work")
    tracker = commands.add_parser("tracker", help="workset trackers (tracker and full modes)")
    tracker_actions = tracker.add_subparsers(dest="action", required=True)
    new = tracker_actions.add_parser("new")
    new.add_argument("--id", required=True)
    new.add_argument("--title", required=True)
    status = tracker_actions.add_parser("status")
    status.add_argument("--id", required=True)
    status.add_argument("--status", choices=TRACKER_STATES, required=True)
    status.add_argument("--evidence", default="")
    status.add_argument("--contract", help="exact gate Task Contract required for DONE unless bound to this session")
    archive = tracker_actions.add_parser("archive")
    archive.add_argument("--id")
    archive_choice = archive.add_mutually_exclusive_group(required=True)
    archive_choice.add_argument("--dry-run", action="store_true")
    archive_choice.add_argument("--apply", action="store_true")
    queue = commands.add_parser("queue", help="full mode's lease-backed queue")
    actions = queue.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    history = actions.add_parser("history")
    history.add_argument("--id")
    claim = actions.add_parser("claim-next")
    claim.add_argument("--agent", required=True)
    claim.add_argument("--request-id", required=True)
    exact_claim = actions.add_parser("claim")
    exact_claim.add_argument("--id", required=True)
    exact_claim.add_argument("--agent", required=True)
    exact_claim.add_argument("--request-id", required=True)
    for action in ("heartbeat", "release", "complete"):
        command = actions.add_parser(action)
        command.add_argument("--id", required=True)
        command.add_argument("--token", required=True)
        if action == "complete":
            command.add_argument("--evidence", required=True)


def run(root, args):
    """Dispatch a parsed mode/tracker/queue command; return the exit code."""
    try:
        if args.command == "mode":
            if args.action == "configure":
                configure(root, args.mode, args.execution, contract_lifetime=args.contract_lifetime)
            elif args.action == "downgrade":
                return downgrade(root, args.mode, args.apply, args.keep_pending)
            elif args.action == "show":
                print(json.dumps(config(root)))
            elif args.action == "check":
                check(root)
            else:
                context_command(root, args)
        elif args.command == "tracker":
            tracker_command(root, args)
        else:
            queue_command(root, args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"workflow error: {error}", file=sys.stderr)
        return 2
    return 0
