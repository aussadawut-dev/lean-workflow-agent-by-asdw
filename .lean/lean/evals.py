"""Model evals: run candidate models on the graded task bank (`.lean/evals/<size>/`), score them with hidden
tests, and propose a size mapping for `.lean/models.json`.

Each run copies one task into a throwaway Git repository in the system temp folder (outside any
repository, so the candidate sees no CLAUDE.md and no task bank), starts the provider CLI as `models.json`
configures it plus EVAL_ARGS (API keys removed, so subscription logins are used), then copies the hidden
tests in and counts passing subtests. A token budget is required and runs reserve tokens before they
start (see evaluate). Tokens follow one rule for every provider: input + cache writes + output, with
cache reads apart (Codex prints one total, used as given); an unknown count is charged exactly its run's
reservation. Results append to `results.jsonl`, so a rerun skips finished runs. The hidden tests run in the
candidate's own Python process, so a solution that patches `unittest` could fake a pass: each run's files
are kept in `solutions/` and its CLI output in `logs/`, so reviewers can read the runs a proposal uses.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

from . import models, spawn
from .util import LeanError, read_json

BANK = Path(__file__).resolve().parents[1] / "evals"
PROMPT = ("Read README.md and complete the task in this repository. You may run the visible tests. "
          "Do not read or create files outside this directory. When done, reply with one line: what you changed.")
PER_PROVIDER = 2  # Runs at once per provider: subscription rate limits, not CPU, are the bottleneck.
ESTIMATE = 250_000  # Tokens reserved per run until a real count is known (the 2026-10-27 eval peaked near 234k).
# Eval-only CLI flags, never written to any settings: Claude's headless mode may run the visible tests.
EVAL_ARGS = {"claude": ["--allowedTools", "Bash(python3 -m unittest:*)"]}
GRADER = r'''
import io, json, sys, unittest
repo, hidden = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
counts = {"passed": 0, "failed": 0}


class Result(unittest.TextTestResult):
    def addSubTest(self, test, sub, err):
        counts["failed" if err else "passed"] += 1
        super().addSubTest(test, sub, err)

    def addError(self, test, err):
        counts["failed"] += 1
        super().addError(test, err)


try:
    suite = unittest.TestLoader().discover(hidden, pattern="test_hidden*.py", top_level_dir=hidden)
    unittest.TextTestRunner(stream=io.StringIO(), resultclass=Result).run(suite)
except Exception as error:  # An unimportable solution scores zero.
    counts["error"] = repr(error)[:200]
print(json.dumps(counts), flush=True)
import os
os._exit(0)  # A thread the solution left running must not hold the grader open.
'''


def index():
    """{size: {"title", "units", "baseline"}} for the shipped task bank."""
    data = read_json(BANK / "index.json")
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, dict) or any(size not in models.TIERS for size in tasks):
        raise LeanError(f"invalid task bank index: {BANK / 'index.json'}")
    return tasks


def prepare(size, destination, overlay=None):
    """A fresh Git repository holding the task for `size` (plus `overlay` files on top, for the reference)."""
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(BANK / size / "task", destination)
    if overlay is not None:
        shutil.copytree(overlay, destination, dirs_exist_ok=True)
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=lean-eval", "-c", "user.email=eval@lean.invalid",
                                                 "commit", "-qm", "task"]):
        subprocess.run(["git", *args], cwd=destination, check=True, capture_output=True)
    return destination


def grade(repo, size, timeout=120, env=None):
    """(passed, failed, error) of the hidden tests for `size` against `repo`; never raises for what a candidate
    left behind (odd output, a file where the hidden folder goes, unwritable files): those score zero."""
    hidden = repo / ".lean-eval-hidden"
    try:
        if hidden.is_symlink() or hidden.is_file():
            hidden.unlink()
        elif hidden.exists():
            shutil.rmtree(hidden)
        shutil.copytree(BANK / size / "hidden", hidden)
        result = subprocess.run([sys.executable, "-I", "-c", GRADER, str(repo), str(hidden)], cwd=repo, text=True,
                                capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL, env=env)
        lines = result.stdout.strip().splitlines()
        counts = json.loads(lines[-1]) if lines else None
        if not isinstance(counts, dict):
            counts = {"error": (result.stderr or "no grader output")[-200:]}
    except subprocess.TimeoutExpired:
        counts = {"error": "hidden tests timed out"}
    except (ValueError, OSError, shutil.Error) as error:
        counts = {"error": f"grading failed: {error!r}"[:200]}
    finally:
        shutil.rmtree(hidden, ignore_errors=True)
    passed, failed = counts.get("passed", 0), counts.get("failed", 0)
    return (passed if type(passed) is int else 0), (failed if type(failed) is int else 0), counts.get("error")


def check_bank(workdir):
    """For every size: (reference score, stub score, units in the index). Reference must be full, stub lower."""
    report, tasks = {}, index()
    for size in models.TIERS:
        if size not in tasks:
            continue
        reference = prepare(size, workdir / size / "reference", overlay=BANK / size / "reference")
        stub = prepare(size, workdir / size / "stub")
        report[size] = (grade(reference, size)[0], grade(stub, size)[0], tasks[size]["units"])
    return report


def tokens(provider, output):
    """(processed tokens or None, cache-read tokens or None) from a provider CLI's output."""
    if provider == "codex":
        found = re.findall(r"tokens used\s*\n\s*([\d,]+)", output)
        return (int(found[-1].replace(",", "")) if found else None), None
    usage = None
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and isinstance(value.get("usage"), dict):
                usage = value["usage"]
                break
    if usage is None:
        return None, None

    def number(name):
        value = usage.get(name, 0)
        return value if type(value) is int else 0

    if provider == "claude":
        return (number("input_tokens") + number("cache_creation_input_tokens") + number("output_tokens"),
                number("cache_read_input_tokens"))
    cached = number("cache_read_tokens")
    return number("total_tokens") - cached, cached


def denied(output):
    """Whether the CLI reports tools it was not allowed to use (agy headless, Claude -p)."""
    return bool(re.search(r'"(denied_actions|permission_denials)"\s*:\s*\[\s*\{', output))


def load_plan(path, data):
    plan = read_json(path)
    if not isinstance(plan, dict) or not isinstance(plan.get("candidates"), list) or not plan["candidates"]:
        raise LeanError("eval plan needs a non-empty candidates list")
    tasks = plan.get("tasks", list(index()))
    if not isinstance(tasks, list) or not tasks or any(size not in index() for size in tasks):
        raise LeanError(f"eval plan tasks must be sizes in the task bank: {', '.join(index())}")
    for candidate in plan["candidates"]:
        if (not isinstance(candidate, dict) or candidate.get("provider") not in data["providers"]
                or not isinstance(candidate.get("model"), str) or not candidate["model"]
                or not (candidate.get("effort") is None or isinstance(candidate.get("effort"), str))):
            raise LeanError(f"invalid candidate {candidate!r}: needs a configured provider, a model and an effort or null")
    return plan["candidates"], tasks


def run_id(candidate, size):
    return f"{candidate['provider']}:{candidate['model']}:{candidate.get('effort')}:{size}"


def work_folder(out, root=None):
    """Where the runs happen: outside any repository, so a candidate sees only its task (no CLAUDE.md, no bank).
    One folder per results folder: its name carries a hash of the resolved `out` path."""
    out = Path(out).resolve()
    tag = hashlib.sha256(str(out).encode()).hexdigest()[:10]
    return Path(root or tempfile.gettempdir()) / "lean-evals" / f"{out.name}-{tag}"


def run_cli(command, repo, env, timeout):
    """(output, exit code, "timeout", "error" or "not-run"). Only a CLI that could not be started is "not-run";
    once it has started, any failure (a timeout, output that is not text) still counts as a started run.
    A timeout kills the CLI's whole process group."""
    try:
        process = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
    except OSError as error:
        return str(error), "not-run"

    def text(parts):
        return "\n".join((part or b"").decode("utf-8", errors="replace") for part in parts)

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        try:  # Anything the CLI left running in its group stops with it.
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        return text((stdout, stderr)), process.returncode
    except subprocess.TimeoutExpired:
        code = "timeout"
    except Exception as error:  # noqa: BLE001 - started: report it, never as "not-run".
        code, note = "error", repr(error)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        pass
    try:  # A process outside the group may still hold the pipes: do not wait for it for ever.
        stdout, stderr = process.communicate(timeout=30)
        output = text((stdout, stderr))
    except Exception:  # noqa: BLE001
        output = ""
    return (output + (f"\n{note}" if code == "error" else "")), code


def evaluate(root, plan_path, budget, out, jobs=4, timeout=900, environment=None, estimate=ESTIMATE, work_root=None,
             stop=None):
    """Run the plan within `budget` tokens; returns (rows of this results file, skipped run ids).

    Before a run starts it reserves max(largest count seen, `estimate`); it starts only while what is
    spent plus every reservation fits the budget, waits while other runs still hold reservations, and is
    skipped only when nothing is in flight and it still does not fit. The budget can be exceeded only by
    runs whose reported count is above their reservation, by at most the sum of those excesses: an unknown
    count is charged exactly its own reservation, and a CLI that never started is charged nothing and is
    retried on the next run. A run that fails in any step is recorded and releases its reservation. Once
    `stop` (a threading.Event, set on Ctrl-C) is set, no further run starts; running ones finish."""
    if type(budget) is not int or budget < 1:
        raise LeanError("--budget must be a positive whole number of tokens")
    if type(estimate) is not int or estimate < 1:
        raise LeanError("--estimate must be a positive whole number of tokens")
    root, out = Path(root), Path(out)
    data = models.load(root)
    candidates, tasks = load_plan(plan_path, data)
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    log = out / "results.jsonl"
    rows = []
    for line in log.read_text().splitlines() if log.exists() else []:
        try:
            row = json.loads(line)
        except ValueError:
            continue  # A line cut short by a crash: that run is simply run again.
        if isinstance(row, dict) and "id" in row and row.get("exit") != "not-run":  # Never started: run again.
            rows.append(row)
    finished = {row["id"] for row in rows}
    state = {"spent": sum(row.get("charged", 0) for row in rows), "reserved": 0,
             "largest": max([row["tokens"] for row in rows if row.get("tokens")] or [0])}
    lock, skipped = threading.Condition(), []
    stop = stop or threading.Event()
    gates = {name: threading.Semaphore(PER_PROVIDER) for name in data["providers"]}
    env, _ = spawn.child_environment(environment=environment)
    for name in [name for name in env if name.startswith("LEAN_") or name == "CLAUDE_PROJECT_DIR"]:
        env.pop(name)
    units = {size: index()[size]["units"] for size in tasks}
    work = work_folder(out, work_root)

    def one(job):
        candidate, size = job
        rid = run_id(candidate, size)
        if rid in finished or stop.is_set():
            return
        with gates[candidate["provider"]]:
            with lock:
                while True:
                    if stop.is_set():  # Checked again after waiting for the gate or for budget.
                        return
                    reserve = max(state["largest"], estimate)
                    if state["spent"] + state["reserved"] + reserve <= budget:
                        break
                    if not state["reserved"]:  # Nothing in flight will free room: it can never fit.
                        skipped.append(rid)
                        return
                    lock.wait()
                state["reserved"] += reserve
            result = None
            try:
                result = attempt(candidate, size, re.sub(r"[^\w.-]", "_", rid))
            finally:  # Release the reservation and charge in one step, whatever happened, so no waiter hangs.
                with lock:
                    try:
                        state["reserved"] -= reserve
                        if result is not None:
                            record(rid, candidate, size, reserve, *result)
                    finally:
                        lock.notify_all()

    def attempt(candidate, size, name):
        """(exit, seconds, output, tokens, cache reads, passed, error); errors are results, not exceptions."""
        output, code, seconds, used, cached, passed, error = "", "not-run", 0.0, None, None, 0, None
        repo = work / name
        try:
            prepare(size, repo)
            command = spawn.command_for(data, candidate["provider"], PROMPT, candidate["model"],
                                        candidate.get("effort"), timeout) + EVAL_ARGS.get(candidate["provider"], [])
            began = time.monotonic()
            output, code = run_cli(command, repo, env, timeout)
            seconds = round(time.monotonic() - began, 1)
            used, cached = tokens(candidate["provider"], output)
            passed, _, error = grade(repo, size, env=env)
        except Exception as failure:  # noqa: BLE001 - one broken run must not stop the eval or hold its reservation.
            error = f"eval error: {failure!r}"[:200]
        finally:
            try:
                (out / "logs" / (name + ".log")).write_text(output)
                if repo.is_dir():  # The solution as left, for review (Git data and hidden tests excluded).
                    shutil.copytree(repo, out / "solutions" / name, dirs_exist_ok=True, symlinks=True,
                                    ignore=shutil.ignore_patterns(".git", ".lean-eval-hidden", "__pycache__"))
            except Exception:  # noqa: BLE001 - keeping logs must never lose the run's record.
                pass
            shutil.rmtree(repo, ignore_errors=True)
        return code, seconds, output, used, cached, passed, error

    def record(rid, candidate, size, reserve, code, seconds, output, used, cached, passed, error):
        """Charge and log one run; the caller holds the lock. A CLI that never started costs nothing; an
        unknown count costs exactly this run's reservation."""
        charged = 0 if code == "not-run" else (used if used is not None else reserve)
        state["largest"] = max(state["largest"], used or 0)
        state["spent"] += charged
        row = {"id": rid, **candidate, "size": size, "exit": code, "seconds": seconds, "tokens": used,
               "cache_read": cached, "charged": charged, "tokens_estimated": used is None and code != "not-run",
               "passed": passed, "units": units[size], "denied": denied(output)}
        if error:
            row["grade_error"] = error
        rows.append(row)
        try:
            with log.open("a") as handle:
                handle.write(json.dumps(row) + "\n")
        except OSError:
            pass
        try:
            print(f"{rid}: {passed}/{units[size]} in {seconds}s, tokens {used if used is not None else '?'}"
                  f" (spent {state['spent']}/{budget})", flush=True)
        except (OSError, ValueError):  # A closed pipe (`| head`) must not stop the eval.
            pass

    pool = ThreadPoolExecutor(max_workers=max(1, jobs))
    futures = [pool.submit(one, (candidate, size)) for size in tasks for candidate in candidates]
    try:
        for future in futures:
            future.result()
    except BaseException:  # Ctrl-C or a bug: start nothing more; running CLIs finish and are recorded.
        stop.set()
        with lock:
            lock.notify_all()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return rows, skipped


def propose(rows):
    """{provider: {size: {"model", "effort"}}}: the fastest full-score candidate per provider and size."""
    best = {}
    for row in rows:
        if row.get("passed") != row.get("units") or row.get("exit") != 0:
            continue  # A denied tool is a note: the score already shows what the run achieved.
        key = (row["provider"], row["size"])
        if key not in best or row["seconds"] < best[key]["seconds"]:
            best[key] = row
    proposal = {}
    for (provider, size), row in sorted(best.items(), key=lambda item: (item[0][0], models.TIERS.index(item[0][1]))):
        proposal.setdefault(provider, {})[size] = {"model": row["model"], "effort": row.get("effort")}
    return proposal


def summary(rows, skipped, budget, work=None):
    """Markdown: per-size results, budget use and what was skipped."""
    spent = sum(row.get("charged", 0) for row in rows)
    lines = ["# Model eval results", "", f"Budget {budget} tokens; charged {spent}. Each run reserved the larger of "
             "the largest count seen and the per-run estimate before it started, so only a run that used more "
             "than its reservation can have gone over. A run with no reported count is charged its own reservation. Times compare across "
             "providers; tokens do not. Raw CLI output is in `logs/`.", ""]
    for size in models.TIERS:
        sized = sorted((row for row in rows if row["size"] == size), key=lambda row: (-row["passed"], row["seconds"]))
        if not sized:
            continue
        lines += [f"## {size}", "", "| Provider | Model | Effort | Score | Time | Tokens | Note |", "|---|---|---|---:|---:|---:|---|"]
        for row in sized:
            note = "; ".join(filter(None, ["permission denied" if row.get("denied") else "",
                                           f"exit {row['exit']}" if row["exit"] != 0 else "",
                                           "tokens estimated" if row.get("tokens_estimated") else ""]))
            lines.append(f"| {row['provider']} | {row['model']} | {row.get('effort') or '-'} | {row['passed']}/{row['units']} "
                         f"| {row['seconds']} s | {row['tokens'] if row['tokens'] is not None else '?'} | {note} |")
        lines.append("")
    if any(row.get("denied") for row in rows):
        lines += ["Some runs were denied tool permissions (headless CLIs cannot ask); see `logs/`. For agy, the user "
                  "adds allow rules (`command(python3)`, `command(git)`, read-only commands, `write_file(" + str(work or "<run folder>")
                  + ")`) under `permissions.allow` in `~/.gemini/antigravity-cli/settings.json`.", ""]
    if skipped:
        lines += [f"Skipped at the budget ({len(skipped)}): " + ", ".join(skipped), ""]
    return "\n".join(lines)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def apply(root, proposal_path, expected):
    """Write the proposed tiers into models.json when the proposal still has the approved digest; returns diff lines."""
    if digest(proposal_path) != expected:
        raise LeanError("proposal changed since it was approved (sha256 differs); review it again")
    proposal = read_json(proposal_path)
    path = Path(root) / models.FILE
    data = models.load(root)
    if not isinstance(proposal, dict):
        raise LeanError("proposal must be an object of providers")
    changes = []
    for provider, tiers in proposal.items():
        if provider not in data["providers"] or not isinstance(tiers, dict):
            raise LeanError(f"proposal names an unconfigured provider: {provider!r}")
        for size, value in tiers.items():
            if size not in models.TIERS or not isinstance(value, dict):
                raise LeanError(f"proposal has an invalid size {size!r} for {provider}")
            old = data["providers"][provider]["tiers"].get(size)
            new = {"model": value.get("model"), "effort": value.get("effort")}
            if old != new:
                changes.append(f"{provider}.{size}: {describe(old)} -> {describe(new)}")
                data["providers"][provider]["tiers"][size] = new
    problems = models.validate(data)
    if problems:
        raise LeanError("the proposal would make an invalid model list: " + "; ".join(problems))
    if changes:
        data["checked"] = time.strftime("%Y-%m-%d")
        path.write_text(models.dumps(data))
    return changes


def describe(value):
    if not value:
        return "(none)"
    return value["model"] + (f" / {value['effort']}" if value.get("effort") else "")


def write_outputs(out, rows, skipped, budget):
    """summary.md and proposal.json in `out`; returns the proposal's sha256."""
    out = Path(out)
    (out / "summary.md").write_text(summary(rows, skipped, budget, work_folder(out)))
    (out / "proposal.json").write_text(json.dumps(propose(rows), indent=2) + "\n")
    return digest(out / "proposal.json")
