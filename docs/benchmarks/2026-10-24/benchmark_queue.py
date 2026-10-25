#!/usr/bin/env python3
"""Compare two workflow.py revisions on disposable full-mode records, without model calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def fixture(root, size, shared, tracker_files=None):
    tracker_files = size if tracker_files is None else tracker_files
    for name in (".lean", "docs/tracking", "docs/history/agent-workflow/2026", ".agents/queue/items"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / ".lean/config.json").write_text(json.dumps({"mode": "full", "configured": True, "execution": "direct"}))
    (root / ".gitignore").write_text(".agent-runtime/\n")
    for name in ("docs/tracking/README.md", "docs/tracking/TEMPLATE.md", ".agents/queue/README.md"):
        (root / name).write_text("Benchmark fixture\n")
    for n in range(1, tracker_files + 1):
        tracker = f"TCK{n:03d}"
        directory = "docs/tracking" if n % 2 else "docs/history/agent-workflow/2026"
        if shared and n > 1:
            directory = "docs/history/agent-workflow/2026"
        status = "DONE" if n <= size and (not shared or n == 1) else "PLANNED"
        (root / directory / f"{tracker}-task.md").write_text(f"# Task\nStatus: {status}\n\n## Evidence\n- checked\n")
    for n in range(1, size + 1):
        tracker = f"TCK{n:03d}"
        item = {"id": f"Q{n:04d}", "tracker": "TCK001" if shared else tracker, "title": "Task",
                "status": "DONE", "dependencies": [], "scopes": [f"area:{n}"], "evidence": "checked"}
        (root / ".agents/queue/items" / f"Q{n:04d}.json").write_text(json.dumps(item))


def run(script, root):
    began = time.perf_counter()
    result = subprocess.run([sys.executable, str(script), "--root", str(root), "check"],
                            capture_output=True, text=True, check=True)
    seconds = time.perf_counter() - began
    if result.stdout != "workflow ok: full\n" or result.stderr:
        raise RuntimeError(f"unexpected validation output: {result.stdout!r} {result.stderr!r}")
    return seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 100, 1000])
    parser.add_argument("--cases", nargs="+", metavar="ITEMS:TRACKERS",
                        help="explicit queue/tracker counts, e.g. 0:10 1:10000 10:10000 1000:1000")
    args = parser.parse_args()
    cases = [(size, size) for size in args.sizes]
    if args.cases:
        try:
            cases = [tuple(map(int, case.split(":"))) for case in args.cases]
            if any(len(case) != 2 or case[0] < 0 or case[1] < max(1, case[0]) for case in cases):
                raise ValueError()
        except ValueError:
            parser.error("cases require nonnegative ITEMS and TRACKERS >= max(1, ITEMS)")
    if args.runs < 1 or any(size < 1 for size in args.sizes):
        parser.error("runs and sizes must be positive")
    scripts = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    report = {"python": sys.version, "platform": platform.platform(), "cpus": os.cpu_count(),
              "source_sha256": {label: hashlib.sha256(path.read_bytes()).hexdigest() for label, path in scripts.items()},
              "method": "One warm-up per version/case; sequential pairs alternate order; fixture setup excluded; CLI startup included.",
              "cases": []}
    for size, tracker_files in cases:
        for shared in (True, False):
            with tempfile.TemporaryDirectory(prefix="lean queue benchmark ") as directory:
                root = Path(directory)
                fixture(root, size, shared, tracker_files)
                before = snapshot(root)
                for script in scripts.values():
                    run(script, root)
                samples = []
                for pair in range(args.runs):
                    for label in (list(scripts) if pair % 2 == 0 else list(reversed(scripts))):
                        load = os.getloadavg()[0]
                        samples.append({"pair": pair + 1, "version": label, "load_before": load,
                                        "seconds": run(scripts[label], root)})
                if snapshot(root) != before:
                    raise RuntimeError("read-only check changed fixture files")
                medians = {label: statistics.median(s["seconds"] for s in samples if s["version"] == label)
                           for label in scripts}
                case = {"items": size, "tracker_files": tracker_files, "layout": "shared" if shared else "distinct",
                        "samples": samples, "median_seconds": medians, "records_unchanged": True}
                report["cases"].append(case)
                print(json.dumps({key: value for key, value in case.items() if key != "samples"}), flush=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
