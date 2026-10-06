#!/usr/bin/env python3
"""Configure Lean modes and manage the full mode's local queue leases."""

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
import sys
import tempfile
import time
import uuid

MODES = ("standard", "tracker", "full")
EXECUTIONS = ("direct", "delegated")
TRACKER_STATES = ("PLANNED", "IN_PROGRESS", "VALIDATING", "REVIEWING", "DONE", "BLOCKED", "FAILED")
LEASE_SECONDS = 30 * 60
ID = re.compile(r"Q[0-9]{4,}")
TRACKER = re.compile(r"TCK[0-9]{3,}")
REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}")
CHECKLIST_HEADING = re.compile(r"(?:acceptance criteri(?:a|on)|tasks?)\b", re.IGNORECASE)
CHECKBOX = re.compile(r"[ \t]*(?:[-+*]|[0-9]+[.)])[ \t]+\[([ xX])\][ \t]*(.*)")


def fail(message):
    raise ValueError(message)


def validate_project_paths(root):
    """Keep workflow data and its parents in this checkout before any mutation.

    Local CLI locking coordinates cooperating processes; it does not protect
    against another process replacing filesystem paths during an operation.
    """
    for relative in (".lean/config.json", ".gitignore", ".agent-runtime", "docs/tracking", ".agents/queue"):
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
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as out:
        out.write(value)
        temporary = Path(out.name)
    os.replace(temporary, path)


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
    return value


def mode_at_least(root, minimum):
    mode = config(root)["mode"]
    if MODES.index(mode) < MODES.index(minimum):
        fail(f"{minimum} mode required; current mode is {mode}")


def configure(root, mode, execution=None):
    with locked(root):
        configure_locked(root, mode, execution)


def configure_locked(root, mode, execution=None):
    current = config(root)
    if MODES.index(mode) < MODES.index(current["mode"]):
        fail("mode downgrade is not automatic; resolve existing tracking and claims first")
    if mode in ("tracker", "full"):
        tracking = root / "docs/tracking"
        tracking.mkdir(parents=True, exist_ok=True)
        template = tracking / "TEMPLATE.md"
        if not template.exists():
            template.write_text((root / ".lean/templates/tracker.md").read_text())
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
                "dependencies, and exclusive scopes. Use `.lean/scripts/workflow.py queue claim --id QNNNN --agent NAME --request-id UUID`, "
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
    write_json(root / ".lean/config.json", current)
    print(f"mode: {mode}")


def tracker_file(root, tracker_id):
    if not TRACKER.fullmatch(tracker_id):
        fail("invalid tracker id")
    directory = root / "docs/tracking"
    matches = [p for p in directory.glob(f"{tracker_id}*.md")
               if p.stem == tracker_id or p.stem.startswith(tracker_id + "-")]
    if len(matches) != 1:
        fail(f"expected one tracker document for {tracker_id}, found {len(matches)}")
    return matches[0]


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
            content = (root / ".lean/templates/tracker.md").read_text()
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
                fail(f"expected one Status line: {args.id}")
            if args.status == "DONE" and not evidence:
                fail("DONE requires evidence")
            if args.status == "DONE" and unchecked_tracker_items(content):
                fail(f"DONE requires all acceptance criteria and tasks checked: {args.id}")
            if args.status == "DONE" and config(root)["mode"] == "full":
                linked = [item for item in items(root).values() if item["tracker"] == args.id]
                if not linked or any(item["status"] != "DONE" for item in linked):
                    fail("all linked queue items must be DONE before the tracker")
            content = content[:matches[0].start()] + f"Status: {args.status}" + content[matches[0].end():]
            if evidence:
                marker = "## Evidence\n"
                if marker not in content:
                    fail(f"missing Evidence section: {args.id}")
                content = content.replace(marker, marker + f"\n- {evidence}\n", 1)
            write_text(path, content)
            print(f"tracker {args.id}: {args.status}")


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
        tracker_file(root, value["tracker"])
        for field in ("created_at", "completed_at"):
            if field in value:
                timestamp(value[field])
        for field in ("dependencies", "scopes"):
            if not isinstance(value.get(field), list) or not all(isinstance(x, str) for x in value[field]):
                fail(f"invalid {field}: {item_id}")
        if not value["scopes"] or len(set(value["scopes"])) != len(value["scopes"]):
            fail(f"missing or repeated scope: {item_id}")
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


def clean_queue(root, selection, apply=False):
    with locked(root, read_only=not apply):
        current = config(root)
        history = queue_history(root)
        directory = root / ".agents/queue/items"
        if directory.exists() or history:
            _, all_items, claims = validate_records(root, current["mode"], include_retained=True)
        else:
            all_items, claims = {}, active_claims(root, cleanup=False)
            validate_claims(all_items, claims)
        cutoff = time.time() - 30 * 86400
        selected, resumed, unknown = [], [], []
        for path in sorted(directory.glob("*.json")):
            item_id = path.stem
            item = all_items[item_id]
            if item_id in history:
                resumed.append(item_id)
                continue
            if item["status"] != "DONE":
                continue
            if selection == "old" and "completed_at" not in item:
                unknown.append(item_id)
                continue
            if selection == "all" or timestamp(item["completed_at"]) < cutoff:
                selected.append(item_id)
        report = {"selection": selection, "older_than_days": 30 if selection == "old" else None,
                  "selected": selected, "resumed": resumed, "unknown_age": unknown,
                  "archived": [], "applied": apply}
        # Per-item commit: publish and sync full snapshot before removing source.
        # A failed batch can be retried; earlier snapshots remain valid history.
        if apply:
            for item_id in selected + resumed:
                path = directory / (item_id + ".json")
                if item_id in claims:
                    fail(f"active claim blocks cleanup: {item_id}")
                if item_id not in history:
                    content = path.read_bytes().decode("utf-8")
                    record = {"version": 1, "archived_at": utc_now(), "reason": selection,
                              "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                              "content": content}
                    destination = root / ".agents/queue/history" / (item_id + ".json")
                    write_json(destination, record)
                destination = root / ".agents/queue/history" / (item_id + ".json")
                # Sync recovery snapshots too: a prior attempt may have failed at fsync.
                with destination.open("rb") as snapshot:
                    os.fsync(snapshot.fileno())
                for parent in (destination.parent, destination.parent.parent):
                    descriptor = os.open(str(parent), os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                path.unlink()
                report["archived"].append(item_id)
        print(json.dumps(report, indent=2))
        return 0


def validate_records(root, mode, include_retained=False):
    """Read-only validation; callers hold the workflow lock when applying changes."""
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
                fail(f"invalid tracker status: {path}")
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
        overlap = scopes.intersection(item["scopes"])
        if overlap:
            fail(f"overlapping active claim scope: {sorted(overlap)[0]}")
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
                if occupied.intersection(item["scopes"]):
                    continue
                claim = {"id": item_id, "agent": args.agent, "request_id": args.request_id,
                         "token": uuid.uuid4().hex,
                         "expires_at": time.time() + LEASE_SECONDS}
                write_json(root / ".agent-runtime/claims" / f"{item_id}.json", claim)
                print(json.dumps(claim))
                return
            fail("no claimable queue item")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure")
    setup.add_argument("mode", choices=MODES)
    setup.add_argument("--execution", choices=EXECUTIONS)
    lower = commands.add_parser("downgrade")
    lower.add_argument("mode", choices=MODES)
    choice = lower.add_mutually_exclusive_group(required=True)
    choice.add_argument("--dry-run", action="store_true")
    choice.add_argument("--apply", action="store_true")
    lower.add_argument("--keep-pending", action="store_true")
    clean = commands.add_parser("clean-queue")
    clean.add_argument("selection", choices=("old", "all"))
    clean_choice = clean.add_mutually_exclusive_group(required=True)
    clean_choice.add_argument("--dry-run", action="store_true")
    clean_choice.add_argument("--apply", action="store_true")
    commands.add_parser("show")
    commands.add_parser("check")
    tracker = commands.add_parser("tracker")
    tracker_actions = tracker.add_subparsers(dest="action", required=True)
    new = tracker_actions.add_parser("new")
    new.add_argument("--id", required=True)
    new.add_argument("--title", required=True)
    status = tracker_actions.add_parser("status")
    status.add_argument("--id", required=True)
    status.add_argument("--status", choices=TRACKER_STATES, required=True)
    status.add_argument("--evidence", default="")
    queue = commands.add_parser("queue")
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
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "configure":
            configure(root, args.mode, args.execution)
        elif args.command == "downgrade":
            return downgrade(root, args.mode, args.apply, args.keep_pending)
        elif args.command == "clean-queue":
            return clean_queue(root, args.selection, args.apply)
        elif args.command == "show":
            print(json.dumps(config(root)))
        elif args.command == "check":
            check(root)
        elif args.command == "tracker":
            tracker_command(root, args)
        else:
            queue_command(root, args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"workflow error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
