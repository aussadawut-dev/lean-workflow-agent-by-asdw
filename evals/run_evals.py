#!/usr/bin/env python3
"""Run Lean behavior evals against real agent sessions.

Paid: every run is a full `claude -p` or `codex exec` session on your own credential.
Nothing runs without --model and a total budget (--max-total-usd for Claude,
--max-total-tokens for Codex); --dry-run builds and checks fixtures only.
"""
import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from cases import CASES
from harness import (PROVIDERS, TEST_COMMAND, build_fixture, changed_files, codex_home, harness_problems,
                     read_transcript, run_agent, tests_pass)

RESULTS = Path(__file__).resolve().parent / "results"


def new_results_dir(base, stamp, provider):
    """A fresh directory per run; runs started in the same second (say, one per provider) never share one."""
    base.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 1000):
        path = base / (f"{stamp}-{provider}" if attempt == 1 else f"{stamp}-{provider}-{attempt}")
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue
    raise SystemExit(f"no free results directory for {stamp}-{provider} under {base}")


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
    parser.add_argument("--provider", choices=PROVIDERS, default="claude", help="agent CLI to drive")
    parser.add_argument("--max-run-usd", type=float, default=2.0, help="per-run budget passed to claude")
    parser.add_argument("--max-total-usd", type=float, help="claude: stop launching runs once spend reaches this")
    parser.add_argument("--max-total-tokens", type=int,
                        help="codex: stop launching runs once reported tokens reach this (no per-run cap)")
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
    codex = args.provider == "codex"
    budget_flag = "--max-total-tokens" if codex else "--max-total-usd"
    limit = args.max_total_tokens if codex else args.max_total_usd
    if not args.model or limit is None:
        parser.error(f"paid runs need --model and {budget_flag} (use --dry-run to check fixtures)")
    if not shutil.which(args.provider):
        print(f"BLOCKED: `{args.provider}` CLI not found", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = new_results_dir(RESULTS, stamp, args.provider)
    spent, tokens, records, partial = 0.0, 0, [], False
    for case in cases:
        for run in range(1, args.runs + 1):
            if (tokens if codex else spent) >= limit:
                partial = True
                break
            directory = tempfile.mkdtemp(prefix=f"lean eval {case['name']} ")
            root = build_fixture(directory, case)
            began = time.monotonic()
            run_budget = None if codex else min(args.max_run_usd, args.max_total_usd - spent)
            label = f"{case['name']}#{run}"
            with (codex_home(root) if codex else contextlib.nullcontext()) as home:
                env = dict(os.environ, CODEX_HOME=str(home)) if home else None
                lines, code, stderr = run_agent(root, case["prompt"], args.model, run_budget, args.timeout,
                                                args.provider, env)
                # Save the raw session first: a paid transcript must survive a parser or grader error.
                (out / f"{label}.jsonl").write_text("\n".join(lines) + "\n")
                # Codex stores the session rollout (spawned agents) in the temporary home.
                transcript = read_transcript(args.provider, lines, home)
            cost = transcript.cost
            spent += cost or 0.0
            tokens += transcript.tokens or 0
            failures = harness_problems(lines)
            failures += grade(case, transcript, root) if transcript.events else ["no session events: " + stderr[-300:]]
            records.append({"case": case["name"], "run": run, "passed": not failures, "failures": failures,
                            "exit_code": code, "cost_usd": cost, "tokens": transcript.tokens, "seconds": round(time.monotonic() - began, 1),
                            "changed_files": changed_files(root), "fixture": directory if args.keep else None})
            usage = f"{transcript.tokens or 0} tokens" if codex else f"${cost or 0:.2f}"
            print(f"{'PASS' if not failures else 'FAIL'} {label} {usage}"
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
    report = {"provider": args.provider, "model": args.model, "requested_runs": args.runs, "partial": partial,
              "spent_usd": round(spent, 4), "spent_tokens": tokens, "summary": summary, "runs": records}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    total = f"{tokens} tokens" if codex else f"${spent:.2f}"
    print(f"\nspent {total} (reported by {args.provider}){'; stopped at budget' if partial else ''}")
    for name, entry in summary.items():
        print(f"{entry['passed']}/{entry['runs']} {name}")
    print(f"report: {out / 'report.json'}")
    return 0 if records and all(record["passed"] for record in records) and not partial else 1


if __name__ == "__main__":
    sys.exit(main())
