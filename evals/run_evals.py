#!/usr/bin/env python3
"""Run Lean behavior evals against real agent sessions.

Paid: every run is a full `claude -p` session on your own credential. Nothing runs
without --model and --max-total-usd; --dry-run builds and checks fixtures only.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from cases import CASES
from harness import TEST_COMMAND, Transcript, build_fixture, changed_files, run_agent, tests_pass

RESULTS = Path(__file__).resolve().parent / "results"


def select(names):
    if not names:
        return CASES
    known = {case["name"]: case for case in CASES}
    missing = [name for name in names if name not in known]
    if missing:
        raise SystemExit(f"unknown case(s): {', '.join(missing)}; known: {', '.join(known)}")
    return [known[name] for name in names]


def dry_run(cases):
    """Build each fixture and confirm it starts clean, with passing tests and the expected gate result."""
    failures = 0
    for case in cases:
        with tempfile.TemporaryDirectory(prefix=f"lean eval {case['name']} ") as directory:
            root = build_fixture(directory, case)
            problems = []
            if changed_files(root):
                problems.append(f"fixture not clean: {changed_files(root)}")
            if not tests_pass(root):
                problems.append(f"`{TEST_COMMAND}` fails on the fixture")
            gate = subprocess.run(["bash", ".lean/scripts/quality-gate.sh", "--root", "."], cwd=root,
                                  capture_output=True, text=True)
            if gate.returncode != case.get("gate_exit", 0):
                problems.append(f"gate exit {gate.returncode}, expected {case.get('gate_exit', 0)}")
            print(f"{'ok  ' if not problems else 'FAIL'} {case['name']}" + "".join(f"\n     {p}" for p in problems))
            failures += bool(problems)
    return 1 if failures else 0


def grade(case, transcript, root):
    failures = []
    for grader in case["graders"]:
        try:
            failures += grader(transcript, root)
        except Exception as error:  # A grader crash is a failed check, not a crashed run.
            failures.append(f"{grader.__name__} crashed: {error!r}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="*", help="case names (default: all)")
    parser.add_argument("--list", action="store_true", help="list cases and exit")
    parser.add_argument("--dry-run", action="store_true", help="build fixtures only; no model calls")
    parser.add_argument("--model", help="model for every run (required unless --dry-run)")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--max-run-usd", type=float, default=2.0, help="per-run budget passed to claude")
    parser.add_argument("--max-total-usd", type=float, help="stop launching runs once spend reaches this")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per run")
    parser.add_argument("--keep", action="store_true", help="keep fixture directories for inspection")
    args = parser.parse_args(argv)
    cases = select(args.cases)
    if args.list:
        for case in CASES:
            print(f"{case['name']}: {case['prompt']}")
        return 0
    if args.dry_run:
        return dry_run(cases)
    if not args.model or args.max_total_usd is None:
        parser.error("paid runs need --model and --max-total-usd (use --dry-run to check fixtures)")
    if not shutil.which("claude"):
        print("BLOCKED: `claude` CLI not found", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS / stamp
    out.mkdir(parents=True)
    spent, records, partial = 0.0, [], False
    for case in cases:
        for run in range(1, args.runs + 1):
            if spent >= args.max_total_usd:
                partial = True
                break
            directory = tempfile.mkdtemp(prefix=f"lean eval {case['name']} ")
            root = build_fixture(directory, case)
            began = time.monotonic()
            lines, code, stderr = run_agent(root, case["prompt"], args.model,
                                            min(args.max_run_usd, args.max_total_usd - spent), args.timeout)
            label = f"{case['name']}#{run}"
            # Save the raw session first: a paid transcript must survive a parser or grader error.
            (out / f"{label}.jsonl").write_text("\n".join(lines) + "\n")
            transcript = Transcript(lines)
            cost = transcript.cost
            spent += cost or 0.0
            failures = grade(case, transcript, root) if transcript.events else ["no session events: " + stderr[-300:]]
            records.append({"case": case["name"], "run": run, "passed": not failures, "failures": failures,
                            "exit_code": code, "cost_usd": cost, "seconds": round(time.monotonic() - began, 1),
                            "changed_files": changed_files(root), "fixture": directory if args.keep else None})
            print(f"{'PASS' if not failures else 'FAIL'} {label} ${cost or 0:.2f}"
                  + "".join(f"\n     {failure}" for failure in failures), flush=True)
            if not args.keep:
                shutil.rmtree(directory, ignore_errors=True)
        if partial:
            break

    summary = {}
    for record in records:
        entry = summary.setdefault(record["case"], {"passed": 0, "runs": 0})
        entry["runs"] += 1
        entry["passed"] += record["passed"]
    report = {"model": args.model, "requested_runs": args.runs, "partial": partial,
              "spent_usd": round(spent, 4), "summary": summary, "runs": records}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nspent ${spent:.2f} (reported by claude){'; stopped at budget' if partial else ''}")
    for name, entry in summary.items():
        print(f"{entry['passed']}/{entry['runs']} {name}")
    print(f"report: {out / 'report.json'}")
    return 0 if records and all(record["passed"] for record in records) and not partial else 1


if __name__ == "__main__":
    sys.exit(main())
