#!/usr/bin/env python3
"""Configure Lean modes and manage the full mode's local queue leases."""

import argparse
import contextlib
import fcntl
import json
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


def fail(message):
    raise ValueError(message)


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
    """Return unchecked AC/TASK items; legacy trackers without these lists remain valid."""
    sections = re.split(r"(?m)^## (.+)$", content)
    unchecked = []
    for index in range(1, len(sections), 2):
        heading, body = sections[index], sections[index + 1]
        if heading.strip().lower() in ("acceptance criteria", "tasks"):
            entries = re.findall(r"(?m)^- \[([ xX])\] ((?:AC|TASK)-[^:]+): (.+)$", body)
            unchecked.extend(entry[1] for entry in entries if entry[0] == " ")
    return unchecked


def tracker_command(root, args):
    mode_at_least(root, "tracker")
    with locked(root):
        if args.action == "new":
            if not TRACKER.fullmatch(args.id) or not args.title.strip():
                fail("valid tracker id and title are required")
            directory = root / "docs/tracking"
            matches = list(directory.glob(f"{args.id}*.md"))
            if any(p.stem == args.id or p.stem.startswith(args.id + "-") for p in matches):
                fail(f"tracker already exists: {args.id}")
            content = (root / ".lean/templates/tracker.md").read_text()
            content = content.replace("TCKNNN — Title", f"{args.id} — {args.title.strip()}", 1)
            path = directory / f"{args.id}.md"
            with path.open("x") as out:
                out.write(content)
            print(f"created: {path.relative_to(root)}")
        elif args.action == "status":
            path = tracker_file(root, args.id)
            content = path.read_text()
            matches = list(re.finditer(r"(?m)^Status: [A-Z_]+$", content))
            if len(matches) != 1:
                fail(f"expected one Status line: {args.id}")
            if args.status == "DONE" and not args.evidence.strip():
                fail("DONE requires evidence")
            if args.status == "DONE" and unchecked_tracker_items(content):
                fail(f"DONE requires all acceptance criteria and tasks checked: {args.id}")
            if args.status == "DONE" and config(root)["mode"] == "full":
                linked = [item for item in items(root).values() if item["tracker"] == args.id]
                if not linked or any(item["status"] != "DONE" for item in linked):
                    fail("all linked queue items must be DONE before the tracker")
            content = content[:matches[0].start()] + f"Status: {args.status}" + content[matches[0].end():]
            if args.evidence.strip():
                marker = "## Evidence\n"
                if marker not in content:
                    fail(f"missing Evidence section: {args.id}")
                content = content.replace(marker, marker + f"\n- {args.evidence.strip()}\n", 1)
            write_text(path, content)
            print(f"tracker {args.id}: {args.status}")


def items(root):
    directory = root / ".agents/queue/items"
    result = {}
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        value = read_json(path)
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


def check(root):
    current = config(root)
    tracker_statuses = {}
    if current["mode"] in ("tracker", "full"):
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
    if current["mode"] == "full":
        if not (root / ".agents/queue/items").is_dir():
            fail("missing queue items directory")
        if not (root / ".agents/queue/README.md").is_file():
            fail("missing queue guide")
        with locked(root):
            all_items = items(root)
            validate_claims(all_items, active_claims(root))
        for tracker_id, status in tracker_statuses.items():
            if status == "DONE":
                linked = [item for item in all_items.values() if item["tracker"] == tracker_id]
                if not linked or any(item["status"] != "DONE" for item in linked):
                    fail(f"DONE tracker has unfinished queue items: {tracker_id}")
    print(f"workflow ok: {current['mode']}")


@contextlib.contextmanager
def locked(root):
    runtime = root / ".agent-runtime"
    runtime.mkdir(exist_ok=True)
    with (runtime / "queue.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def active_claims(root):
    directory = root / ".agent-runtime/claims"
    directory.mkdir(parents=True, exist_ok=True)
    active = {}
    for path in directory.glob("*.json"):
        claim = read_json(path)
        if (not isinstance(claim, dict) or not ID.fullmatch(path.stem)
                or claim.get("id") != path.stem
                or not isinstance(claim.get("agent"), str) or not claim["agent"]
                or not isinstance(claim.get("token"), str) or not claim["token"]
                or not isinstance(claim.get("request_id"), str)
                or not REQUEST_ID.fullmatch(claim["request_id"])
                or not isinstance(claim.get("expires_at"), (int, float))):
            fail(f"invalid claim file: {path}")
        if claim.get("expires_at", 0) <= time.time():
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
        if claim["agent"] in agents:
            fail(f"agent owns multiple claims: {claim['agent']}")
        agents.add(claim["agent"])
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
    if not isinstance(claim, dict) or claim.get("id") != item_id:
        fail(f"invalid claim file for {item_id}")
    if (claim.get("token") != token or not isinstance(claim.get("expires_at"), (int, float))
            or claim["expires_at"] <= time.time()):
        fail(f"invalid or expired claim for {item_id}")
    return path, claim


def queue_command(root, args):
    mode_at_least(root, "full")
    with locked(root):
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
            write_json(item_path, item)
            path.unlink()
            print(f"completed: {args.id}")
            return

        all_items = items(root)
        claims = active_claims(root)
        if args.action == "list":
            validate_claims(all_items, claims)
            for item_id, item in all_items.items():
                owner = claims.get(item_id, {}).get("agent", "-")
                print(f"{item_id} {item['status']} {owner} {item['tracker']} {item['title']}")
            return
        if args.action in ("claim-next", "claim"):
            if not args.agent.strip():
                fail("agent id is required")
            if not REQUEST_ID.fullmatch(args.request_id):
                fail("request id must be a stable random identifier of at least eight characters")
            existing = [(item_id, claim) for item_id, claim in claims.items() if claim["agent"] == args.agent]
            if existing and len(existing) == 1 and existing[0][1]["request_id"] == args.request_id:
                if args.action == "claim-next" or args.id == existing[0][0]:
                    print(json.dumps(existing[0][1]))
                    return
            if existing:
                fail(f"agent already owns an active claim: {args.agent}")
            occupied = validate_claims(all_items, claims)
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
