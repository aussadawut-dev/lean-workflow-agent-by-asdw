"""Model/effort eval: copy the task repo, run one headless CLI agent, grade with hidden tests.

Usage: python3 harness.py <round-name> <task-dir> <hidden-dir> <units> <budget-tokens> <combos.json> [--jobs N]
Writes results/<round>.jsonl (one line per run). Stops launching once the round's budget is spent.
"""
import json, os, re, shutil, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEAN = Path("/Users/x10/orca/workspaces/lean-workflow-agent-by-asdw/feat-refactor-v4/.lean")
sys.path.insert(0, str(LEAN))
from lean import spawn  # noqa: E402  (API_KEYS, child_environment)

PROMPT = ("Read README.md and complete the task in this repository. You may run the visible tests. "
          "Do not read or create files outside this directory. When done, reply with one line: what you changed.")


def command(c, prompt):
    if c["provider"] == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "-m", c["model"], "-c", f"model_reasoning_effort={c['effort']}",
                "--sandbox", "workspace-write", prompt]
    if c["provider"] == "claude":
        return ["claude", "-p", prompt, "--model", c["model"], "--effort", c["effort"], "--permission-mode", "acceptEdits",
                "--allowedTools", "Bash(python3 -m unittest:*)", "--output-format", "json"]
    args = ["agy", "-p", prompt, "--model", c["model"], "--output-format", "json", "--print-timeout", "600s"]
    return args + c.get("extra", [])


def tokens(c, out):
    """(processed tokens, cache-read tokens). Processed = input + cache writes + output; cache reads apart.
    Codex prints one total, used as given."""
    if c["provider"] == "codex":
        m = re.findall(r"tokens used\s*\n\s*([\d,]+)", out)
        return (int(m[-1].replace(",", "")) if m else None), None
    data = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                break
            except ValueError:
                continue
    usage = (data or {}).get("usage") or {}
    if not usage:
        return None, None
    if c["provider"] == "claude":
        return (usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                + usage.get("output_tokens", 0)), usage.get("cache_read_input_tokens", 0)
    cached = usage.get("cache_read_tokens", 0)
    return usage.get("total_tokens", 0) - cached, cached


def main():
    name, task, hidden, units, budget, combos = sys.argv[1:7]
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
    units, budget = int(units), int(budget)
    combos = json.loads(Path(combos).read_text())
    results = HERE / "results"; results.mkdir(exist_ok=True)
    log = results / f"{name}.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    spent = sum(json.loads(l).get("tokens") or 0 for l in log.read_text().splitlines()) if log.exists() else 0
    lock = threading.Lock()
    state = {"spent": spent}
    per_provider = {p: threading.Semaphore(2) for p in ("codex", "claude", "agy")}
    env, _ = spawn.child_environment()
    for k in [k for k in env if k.startswith(("LEAN_", "CLAUDE_PROJECT_DIR"))]:
        env.pop(k)

    def one(c):
        cid = f"{c['provider']}:{c['model']}:{c.get('effort')}"
        if cid in done:
            return
        with lock:
            if state["spent"] >= budget:
                print(f"SKIP budget {cid}", flush=True)
                return
        with per_provider[c["provider"]]:
            repo = HERE / "runs" / name / cid.replace(":", "_")
            shutil.rmtree(repo, ignore_errors=True)
            shutil.copytree(task, repo)
            subprocess.run(["git", "init", "-q"], cwd=repo)
            subprocess.run(["git", "-c", "user.name=e", "-c", "user.email=e@e", "add", "-A"], cwd=repo)
            subprocess.run(["git", "-c", "user.name=e", "-c", "user.email=e@e", "commit", "-qm", "task"], cwd=repo)
            began = time.monotonic()
            try:
                r = subprocess.run(command(c, PROMPT), cwd=repo, env=env, text=True, capture_output=True,
                                   stdin=subprocess.DEVNULL, timeout=900)
                out, code = r.stdout + "\n" + r.stderr, r.returncode
            except subprocess.TimeoutExpired as error:
                out, code = (error.stdout or b"").decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or ""), "timeout"
            seconds = round(time.monotonic() - began, 1)
            (repo.parent / (repo.name + ".log")).write_text(out)
            used, cached = tokens(c, out)
            shutil.rmtree(repo / "hidden", ignore_errors=True)
            shutil.copytree(hidden, repo / "hidden")
            g = subprocess.run([sys.executable, "-I", str(HERE / "grade.py"), str(repo), str(repo / "hidden"), str(units)],
                               text=True, capture_output=True, timeout=120)
            try:
                grade = json.loads(g.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                grade = {"passed": 0, "total": units, "error": g.stderr[-200:]}
            row = {"id": cid, **c, "exit": code, "seconds": seconds, "tokens": used, "cache_read": cached, **grade}
            with lock:
                state["spent"] += used or 0
                with log.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                print(f"{cid}: {grade['passed']}/{units} {seconds}s tokens={used} exit={code} spent={state['spent']}", flush=True)

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(one, combos))


if __name__ == "__main__":
    main()
