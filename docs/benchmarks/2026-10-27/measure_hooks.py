#!/usr/bin/env python3
"""Hook latency of Lean 4.17.1 vs 5.0.0: the commands Claude runs on every prompt, tool call and Stop.

Each version is exported with `git archive` into a fresh repository whose PROJECT gate block is one
trivial command, so the numbers are the workflow's own overhead, not a project's checks. Every hook
command is run exactly as that version's `.claude/settings.json` configures it, with a JSON payload on
stdin, and timed as wall-clock milliseconds (median and p90 of N runs). Offline; stdlib only.

It also times plain workflow commands and the Python and git floors, counts the git calls one Stop
makes, and with --suite times each version's full test suite once (several minutes).

Usage: python3 measure_hooks.py --v4 release/4.17.1 --v5 HEAD [--runs 20] [--suite] > hook-latency.json
"""
import math
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
GATE = "<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n"
CONTRACT = "Contract: risk=LOW quality=STANDARD acceptance=benchmark fixture"
SESSION = "bench-session"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=bench", "-c", "user.email=bench@example.invalid",
                           *args], check=True, capture_output=True, text=True).stdout.strip()


def export(ref, into, trivial_gate=True):
    into.mkdir()
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", ref], check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(into)], input=archive, check=True)
    if not trivial_gate:  # Test suites read the real gate block, so they run on an unmodified export.
        git(into, "init", "-q")
        git(into, "add", "-A")
        git(into, "commit", "-qm", "base")
        return git(ROOT, "rev-parse", f"{ref}^{{commit}}")
    project = into / ".lean/PROJECT.md"
    text = project.read_text()
    start, end = text.index("<!-- gate:start -->"), text.index("<!-- gate:end -->") + len("<!-- gate:end -->\n")
    project.write_text(text[:start] + GATE + text[end:])
    (into / ".gitignore").write_text(((into / ".gitignore").read_text() if (into / ".gitignore").exists() else "")
                                     + "\n.agent-runtime/\n")
    git(into, "init", "-q")
    git(into, "add", "-A")
    git(into, "commit", "-qm", "base")
    return git(ROOT, "rev-parse", f"{ref}^{{commit}}")


def hooks(root):
    settings = json.loads((root / ".claude/settings.json").read_text())
    found = {event: entries[0]["hooks"][0]["command"] for event, entries in settings["hooks"].items()}
    if isinstance(settings.get("statusLine"), dict):
        found["statusLine"] = settings["statusLine"]["command"]
    return found


def run(root, command, payload):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    for name in ("LEAN_GATE_FORCE", "LEAN_GATE_LOCK_FD", "LEAN_GATE_LOCK_TOKEN", "CLAUDE_GATE_FORCE"):
        env.pop(name, None)
    began = time.perf_counter()
    result = subprocess.run(["bash", "-c", command], cwd=root, input=json.dumps(payload), text=True,
                            capture_output=True, env=env)
    return (time.perf_counter() - began) * 1000, result.returncode, result.stdout


def summary(samples):
    ordered = sorted(samples)
    return {"median_ms": round(statistics.median(ordered), 1),
            "p90_ms": round(ordered[max(0, math.ceil(len(ordered) * 0.9) - 1)], 1),  # nearest rank
            "min_ms": round(ordered[0], 1), "runs": len(ordered)}


def measure(root, runs):
    commands = hooks(root)
    base = {"session_id": SESSION, "cwd": str(root), "hook_event_name": ""}
    read = dict(base, tool_name="Read", tool_input={"file_path": str(root / "AGENTS.md")})
    write = dict(base, tool_name="Bash", tool_input={"command": "echo x > work.txt"})
    declare = dict(base, tool_name="Bash", tool_input={"command": f"python3 .lean/bin/lean contract declare --contract '{CONTRACT}'"
                                                      if (root / ".lean/bin/lean").exists() else
                                                      f"python3 .lean/scripts/contract_guard.py declare --contract '{CONTRACT}'"})
    out, codes = {}, {}

    def time_case(name, command, payload, before=None):
        samples = []
        for _ in range(runs):
            if before:
                before()
            elapsed, code, stdout = run(root, command, payload)
            samples.append(elapsed)
            codes.setdefault(name, set()).add(code)
            if name.startswith("stop") and stdout.strip():
                # Claude Stops refuse with a JSON decision on exit 0: a timed Stop must be a silent pass.
                raise SystemExit(f"{root.name} {name}: the Stop did not pass silently: {stdout.strip()[:200]}")
        out[name] = summary(samples)

    time_case("session_start", commands["SessionStart"], dict(base, source="startup"))
    time_case("prompt_submit", commands["UserPromptSubmit"], dict(base, prompt="benchmark prompt"))
    time_case("pre_tool_read", commands["PreToolUse"], read)
    # Bind the contract once (the guard's own declare path), then time a writing tool call that is allowed.
    run(root, commands["PreToolUse"], declare)
    subprocess.run(["bash", "-c", declare["tool_input"]["command"]], cwd=root, capture_output=True,
                   env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
    time_case("pre_tool_write_bound", commands["PreToolUse"], write)
    (root / "work.txt").write_text("change\n")
    stop = dict(base, stop_hook_active=False)

    def cold():
        for name in (".agent-runtime/gate-cache", ".claude/.gate-cache"):
            try:
                (root / name).unlink()
            except OSError:
                pass

    time_case("stop_cold_trivial_gate", commands["Stop"], stop, before=cold)
    run(root, commands["Stop"], stop)
    time_case("stop_cached", commands["Stop"], stop)
    if "statusLine" in commands:
        time_case("status_line", commands["statusLine"], base)
    for name, seen in codes.items():
        out[name]["exit_codes"] = sorted(seen)
    out["stop_git_calls"] = git_calls(root, commands["Stop"], stop)
    return out


def git_calls(root, command, payload):
    """How many git processes one cached Stop starts, through a logging git shim first on PATH."""
    real = subprocess.run(["bash", "-c", "command -v git"], capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory() as shim:
        log = Path(shim) / "calls"
        (Path(shim) / "git").write_text(f'#!/bin/sh\necho x >> "{log}"\nexec "{real}" "$@"\n')
        (Path(shim) / "git").chmod(0o755)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root), PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
        subprocess.run(["bash", "-c", command], cwd=root, input=json.dumps(payload), text=True, capture_output=True,
                       env=env)
        return len(log.read_text().splitlines()) if log.exists() else 0


COMMANDS = {  # Same purpose in both versions.
    "show_mode": (["python3", ".lean/scripts/workflow.py", "show"], ["python3", ".lean/bin/lean", "mode", "show"]),
    "check_records": (["python3", ".lean/scripts/workflow.py", "check"], ["python3", ".lean/bin/lean", "mode", "check"]),
    "check_models": (["python3", ".lean/scripts/model_catalog.py", "check"],
                     ["python3", ".lean/bin/lean", "models", "check"]),
}
SUITES = {"4.17.1": ["python3", ".lean/tests/run_tests.py", "--shards", "6"], "5.0.0": ["python3", ".lean/bin/lean", "test", "--all"]}


def timed(command, cwd, runs):
    samples, codes = [], set()
    for _ in range(runs):
        began = time.perf_counter()
        result = subprocess.run(command, cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL)
        samples.append((time.perf_counter() - began) * 1000)
        codes.add(result.returncode)
    return dict(summary(samples), exit_codes=sorted(codes))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--v4", default="release/4.17.1")
    parser.add_argument("--v5", default="HEAD")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--suite", action="store_true", help="also time each full test suite once")
    args = parser.parse_args()
    result = {"measurement": "Wall-clock ms of each configured Claude hook command; trivial gate (`true`).",
              "python": sys.version.split()[0], "platform": platform.platform(), "runs": args.runs, "versions": {}}
    with tempfile.TemporaryDirectory(prefix="lean-hooks-") as temporary:
        # Each export is a new path, so its bytecode would stay in the user's cache for good; keep it here.
        cache = Path(temporary) / "cache"
        cache.mkdir(mode=0o700)
        os.environ["XDG_CACHE_HOME"] = str(cache)
        for label, ref in (("4.17.1", args.v4), ("5.0.0", args.v5)):
            root = Path(temporary) / label
            commit = export(ref, root)
            index = 0 if label == "4.17.1" else 1
            result["versions"][label] = {
                "ref": ref, "commit": commit, "hooks": hooks(root), "results": measure(root, args.runs),
                "commands": {name: timed(pair[index], root, args.runs) for name, pair in COMMANDS.items()}}
            if args.suite:
                pristine = Path(temporary) / f"{label}-suite"
                export(ref, pristine, trivial_gate=False)
                began = time.perf_counter()
                suite = subprocess.run(SUITES[label], cwd=pristine, capture_output=True, text=True,
                                       stdin=subprocess.DEVNULL)
                elapsed = time.perf_counter() - began
                result["versions"][label]["suite"] = {"command": " ".join(SUITES[label]), "exit_code": suite.returncode,
                                                      "seconds": round(elapsed, 1),
                                                      "last_line": (suite.stdout + suite.stderr).strip().splitlines()[-1:]}
        result["floors"] = {"python_start": timed(["python3", "-c", "pass"], temporary, args.runs),
                            "git_rev_parse": timed(["git", "-C", str(root), "rev-parse", "HEAD"], temporary, args.runs)}
    old, new = (result["versions"][v]["results"] for v in ("4.17.1", "5.0.0"))
    result["delta_median_percent"] = {name: round((new[name]["median_ms"] - old[name]["median_ms"])
                                                  / old[name]["median_ms"] * 100, 1)
                                      for name in old if name in new and isinstance(old[name], dict)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
