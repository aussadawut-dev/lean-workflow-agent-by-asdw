"""Plan and run agents: waves of independent tasks with exclusive file ownership.

Three levels decide how many agents run at once:
  default   at most `max_agents` (1 unless the project raised it), each sized 3S-3XL;
  max       `/lean-agents` alone: one agent per task that can run in parallel;
  explicit  `/lean-agents <model> xN`: up to N agents, all on that model.
`plan` only computes; `run` starts headless provider CLIs in separate git worktrees, using the
subscription login: API keys are removed from each child's environment unless allowed.
"""
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid

from . import models, progress
from .util import LeanError, read_json, runtime, safe_path, write_json

TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# Variables that switch a provider CLI from the subscription login to metered API billing.
API_KEYS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
            "OPENAI_API_KEY", "CODEX_API_KEY", "AZURE_OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
            "GOOGLE_GENAI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS")
DEFAULT_TIMEOUT = 1800
BRIEF = """
---
Lean worker brief (task {id}, run {run}):
- Start your reply with a Task Contract line, as AGENTS.md requires.
- Edit only these files: {files}. Other files are owned by other agents or the Controller.
- Run the tests for what you change; a bug fix needs a regression test that fails before the fix.
- Report progress with `python3 .lean/bin/lean progress set <phase> [--done N --total M]`.
- Do not commit, push or merge. Finish with a handoff: changed files, test evidence, risks.
"""


def load_tasks(source):
    """Validated task list from a JSON file: {"tasks": [{id, files, size, deps?, title?, prompt?}]}."""
    data = read_json(source)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise LeanError("task file needs a non-empty \"tasks\" list")
    seen = {}
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not TASK_ID.fullmatch(task["id"]):
            raise LeanError(f"task id must match {TASK_ID.pattern}: {task!r:.80}")
        if task["id"] in seen:
            raise LeanError(f"duplicate task id: {task['id']}")
        files = task.get("files")
        if not isinstance(files, list) or not files or not all(isinstance(f, str) and f for f in files):
            raise LeanError(f"{task['id']}: files must list the paths it owns")
        if task.get("size", "M") not in models.TIERS:
            raise LeanError(f"{task['id']}: size must be one of {', '.join(models.TIERS)}")
        deps = task.get("deps", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise LeanError(f"{task['id']}: deps must be a list of task ids")
        seen[task["id"]] = task
    for task in tasks:
        for dep in task.get("deps", []):
            if dep not in seen or dep == task["id"]:
                raise LeanError(f"{task['id']}: unknown dependency {dep}")
    return tasks


def waves(tasks, concurrency):
    """Topological waves; a wave holds at most `concurrency` tasks with disjoint files."""
    remaining = {task["id"]: task for task in tasks}
    finished, result = set(), []
    while remaining:
        ready = [task for task in tasks if task["id"] in remaining and set(task.get("deps", [])) <= finished]
        if not ready:
            raise LeanError("dependency cycle among: " + ", ".join(sorted(remaining)))
        wave, owned = [], set()
        for task in ready:
            if concurrency is not None and len(wave) >= concurrency:
                break
            if owned.intersection(task["files"]):
                continue  # Shares a file with a task in this wave: it runs in a later wave.
            wave.append(task)
            owned.update(task["files"])
        result.append(wave)
        for task in wave:
            finished.add(task["id"])
            del remaining[task["id"]]
    return result


def plan(root, tasks, level="default", provider=None, model=None, count=None, effort=None):
    data = models.load(root)
    provider = provider or models.detect_provider(data)
    if provider not in data["providers"]:
        raise LeanError(f"provider {provider!r} is not configured in {models.FILE}")
    notes = []
    if level == "explicit":
        if not model or not count or count < 1:
            raise LeanError("explicit level needs --model and -n N (N >= 1)")
        concurrency = count
    elif level == "max":
        concurrency = None
    elif level == "default":
        concurrency = data["max_agents"]
    else:
        raise LeanError(f"unknown level {level!r}")
    if model and level != "explicit":
        raise LeanError("--model applies only with -n N (explicit level)")
    planned = []
    for wave in waves(tasks, concurrency):
        entries = []
        for task in wave:
            size = task.get("size", "M")
            if model and size in models.TIERS and size not in data["providers"][provider]["tiers"]:
                tier_model, tier_effort = None, None  # The explicit model stands; only its effort is unset.
            else:
                tier_model, tier_effort = models.resolve(data, provider, size)
            entries.append({"id": task["id"], "title": task.get("title", ""), "size": size, "files": task["files"],
                            "deps": task.get("deps", []), "model": model or tier_model,
                            "effort": effort if effort is not None else tier_effort,
                            "prompt": task.get("prompt", task.get("title", ""))})
        planned.append(entries)
    width = max(len(wave) for wave in planned)
    if level == "explicit" and width < count:
        notes.append(f"requested {count} agents, but only {width} tasks can run in parallel "
                     "(dependencies or shared files); spawning {width}".replace("{width}", str(width)))
    if level == "default":
        small = [task["id"] for task in tasks if task.get("size", "M") in ("3S", "2S", "S")]
        if small:
            notes.append("size S (and 2S, 3S) tasks are usually cheaper to finish in the main session: " + ", ".join(small))
    return {"schema": 1, "level": level, "provider": provider, "concurrency": concurrency, "agents": width,
            "waves": planned, "notes": notes}


def child_environment(allow_api_keys=False, environment=None):
    """(environment, removed names): metered API credentials are removed unless allowed."""
    environment = dict(os.environ if environment is None else environment)
    removed = []
    if not allow_api_keys:
        for name in API_KEYS:
            if name in environment:
                removed.append(name)
                del environment[name]
    # A child must take its own gate lock and contract session, not inherit this one's. CLAUDECODE marks
    # Claude's own shell (`lean contract declare` relies on it); a Claude child sets its own.
    environment.pop("LEAN_GATE_LOCK_FD", None)
    environment.pop("CLAUDECODE", None)
    return environment, removed


def command_for(data, provider, prompt, model, effort, timeout, trusted=False):
    spec = data["providers"][provider]
    values = {"{prompt}": prompt, "{model}": model, "{effort}": effort or "", "{timeout}": str(timeout)}
    args = []
    for arg in spec["args"]:
        if "{effort}" in arg and not effort:
            # Drop an effort flag and its value when the tier has none.
            if args and args[-1].startswith("-"):
                args.pop()
            continue
        for key, value in values.items():
            arg = arg.replace(key, value)
        args.append(arg)
    if trusted:
        extra = list(spec.get("trusted_args") or [])
        for index, arg in enumerate(extra):
            # A trusted flag replaces the same flag and value already in args (a later duplicate is ambiguous).
            if arg.startswith("-") and arg in args and index + 1 < len(extra) and not extra[index + 1].startswith("-"):
                position = args.index(arg)
                del args[position:position + 2]
        args += extra
    return [spec["command"], *args]


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if result.returncode:
        raise LeanError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


class Agent:
    def __init__(self, entry, run_dir, run_id):
        self.entry, self.id = entry, entry["id"]
        self.directory = run_dir / self.id
        self.worktree = self.directory / "worktree"
        self.branch = f"lean-spawn/{run_id}/{self.id}"
        self.log = self.directory / "output.log"
        self.process, self.started, self.status, self.code = None, None, "queued", None
        self.note, self.base_tree, self.patch, self.ended = "", None, b"", None

    def finish(self, code):
        """Done only when the agent exited cleanly and changed its worktree; say why otherwise."""
        self.code, self.ended = code, time.monotonic()
        denied = denials(self.log)
        if denied:
            self.note = ("the provider denied tools it needed in headless mode: " + ", ".join(denied)
                         + "; allow them in that provider's permission settings")
        if code != 0:
            self.status = "failed"
        elif not changed(self.worktree):
            self.status = "no-changes"
        else:
            self.status = "done"
            # This agent's own change, from its starting tree (HEAD plus its dependencies' changes).
            self.patch = subprocess.run(["git", "-C", str(self.worktree), "diff", "--binary", self.base_tree,
                                         snapshot_tree(self.worktree)], capture_output=True).stdout

    def stop(self):
        """Kill everything the agent started (its own process group), even after the agent exited."""
        if self.process is None:
            return
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        self.process.wait()

    def row(self, provider, trusted=False):
        state = progress.load(self.worktree) if self.worktree.is_dir() else None
        return {"id": self.id, "provider": provider, "model": self.entry["model"], "status": self.status,
                "exit_code": self.code, "worktree": str(self.worktree), "branch": self.branch,
                "log": str(self.log), "progress": state, "note": self.note, "trusted": trusted}


def snapshot_tree(worktree):
    """The worktree's current content as a tree object (staging everything, runtime state excluded)."""
    subprocess.run(["git", "-C", str(worktree), "add", "-A", "--", ".", ":(exclude).agent-runtime"],
                   capture_output=True)
    return git(worktree, "write-tree").strip()


def changed(worktree):
    """Whether an agent left any change in its worktree, ignoring Lean's runtime state."""
    result = subprocess.run(["git", "-C", str(worktree), "status", "--porcelain", "--untracked-files=all"],
                            capture_output=True, text=True)
    return any(line[3:] and not line[3:].startswith(".agent-runtime/") for line in result.stdout.splitlines())


def denials(log):
    """Tools a provider reported denying, from its JSON result (agy `denied_actions`, Claude `permission_denials`)."""
    try:
        lines = Path(log).read_text(errors="replace").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            result = json.loads(line)
        except ValueError:
            continue
        found = result.get("denied_actions") or result.get("permission_denials") or []
        names = []
        for item in found if isinstance(found, list) else []:
            if isinstance(item, dict):
                names.append(str(item.get("display_name") or item.get("tool_name") or item.get("action") or "?"))
            else:
                names.append(str(item))
        return names
    return []


def run(root, planned, timeout=DEFAULT_TIMEOUT, allow_api_keys=False, allow_dirty=False, show=None,
        trusted=False):
    """Run a plan wave by wave; return the final status document.

    `trusted` (opt-in, never a default) appends each provider's `trusted_args` so agents may run commands
    without asking, which headless runs otherwise deny."""
    root = Path(root).resolve()
    data = models.load(root)
    provider = planned["provider"]
    if not allow_dirty and git(root, "status", "--porcelain").strip():
        raise LeanError("the working tree has uncommitted changes that agents in fresh worktrees would not see; "
                        "commit them first or pass --allow-dirty")
    environment, removed = child_environment(allow_api_keys)
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    run_dir = safe_path(runtime(root), f"spawn/{run_id}")
    run_dir.mkdir(parents=True)
    status_path = safe_path(runtime(root), "spawn/current.json")
    agents = [Agent(entry, run_dir, run_id) for wave in planned["waves"] for entry in wave]
    notes = []
    if removed:
        notes.append("removed metered API credentials from agent environments (subscription login only): "
                      + ", ".join(removed))
    display = show or (lambda text: print(text, file=sys.stderr, flush=True))
    if trusted:
        notes.append("TRUSTED run: agents can run any command on this machine without asking; worktrees isolate "
                     "files in Git, not the machine")
    for note in notes:
        display("lean spawn: " + note)

    def publish():
        document = {"schema": 1, "run": run_id, "provider": provider, "notes": notes,
                    "agents": [agent.row(provider, trusted) for agent in agents]}
        write_json(status_path, document)
        write_json(run_dir / "status.json", document)
        return document

    by_id = {agent.id: agent for agent in agents}

    def closure(agent):
        """Every task this one depends on, directly or not, in plan order."""
        needed, pending = set(), list(agent.entry.get("deps", []))
        while pending:
            task = pending.pop()
            if task not in needed:
                needed.add(task)
                pending += by_id[task].entry.get("deps", [])
        return [other for other in agents if other.id in needed]

    def prepare(agent):
        """Start the worktree from HEAD plus every dependency's change; False when that is impossible."""
        failed = [dep.id for dep in closure(agent) if dep.status != "done"]
        if failed:
            agent.status = "skipped"
            agent.note = "not started: dependency " + ", ".join(failed) + " did not finish"
            return False
        agent.directory.mkdir(parents=True)
        git(root, "worktree", "add", "-q", "-b", agent.branch, str(agent.worktree), "HEAD")
        for dep in closure(agent):
            applied = subprocess.run(["git", "-C", str(agent.worktree), "apply", "--binary"], input=dep.patch,
                                     capture_output=True)
            if applied.returncode:
                agent.status = "skipped"
                agent.note = f"not started: the change of dependency {dep.id} does not apply"
                return False
        agent.base_tree = snapshot_tree(agent.worktree)
        return True

    # The provider's own timeout fires first; the runner kills a child that outlives it by this much.
    grace = min(30, max(1, timeout // 10))
    index = 0
    try:
        for wave in planned["waves"]:
            batch = agents[index:index + len(wave)]
            index += len(wave)
            for agent in batch:
                if not prepare(agent):
                    continue
                prompt = (agent.entry.get("prompt") or agent.entry.get("title") or agent.id) + BRIEF.format(
                    id=agent.id, run=run_id, files=", ".join(agent.entry["files"]))
                command = command_for(data, provider, prompt, agent.entry["model"], agent.entry.get("effort"),
                                      timeout, trusted)
                # The command as run, with the prompt (which may be long or private) replaced by a marker.
                shown = ["<prompt>" if arg == prompt else arg for arg in command]
                (agent.directory / "command.txt").write_text(shlex.join(shown) + "\n")
                with agent.log.open("w") as log:
                    agent.process = subprocess.Popen(command, cwd=agent.worktree, env=environment,
                                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                                     start_new_session=True)
                agent.started, agent.status = time.monotonic(), "running"
            last = None
            while any(agent.status == "running" for agent in batch):
                for agent in batch:
                    if agent.status != "running":
                        continue
                    code = agent.process.poll()
                    if code is not None:
                        agent.stop()  # Leave nothing it started behind.
                        agent.finish(code)
                    elif time.monotonic() - agent.started > timeout + grace:
                        agent.stop()
                        agent.code, agent.status, agent.ended = None, "timeout", time.monotonic()
                frame = "\n".join(progress.agent_line(row) for row in publish()["agents"])
                if frame != last:
                    display(frame)
                    last = frame
                time.sleep(1)
    finally:
        for agent in agents:  # An error mid-run must not leave agents running unrecorded.
            if agent.status == "running":
                agent.stop()
                agent.status, agent.note = "interrupted", "the run stopped before this agent finished"
                agent.ended = time.monotonic()
        publish()
        from . import activity
        for agent in agents:
            seconds = round(agent.ended - agent.started, 1) if agent.started and agent.ended else None
            activity.record(root, "spawn", run=run_id, id=agent.id, provider=provider, model=agent.entry["model"],
                            effort=agent.entry.get("effort"), status=agent.status, seconds=seconds,
                            level=planned.get("level"))
    return publish()


def summary(document):
    lines = [f"spawn run {document['run']} ({document['provider']}):"]
    for row in document["agents"]:
        lines.append(f"  {row['id']}: {row['status']} — worktree {row['worktree']} (branch {row['branch']}); "
                     f"log {row['log']}")
        if row.get("note"):
            lines.append(f"    note: {row['note']}")
    lines.append("Integrate with `git -C <worktree> add -A && git -C <worktree> diff --binary --cached HEAD | "
                 "git apply --binary`, then verify; remove worktrees with `python3 .lean/bin/lean spawn clean <run>`.")
    return "\n".join(lines)


def clean(root, run_id):
    root = Path(root).resolve()
    run_dir = safe_path(runtime(root, create=False), f"spawn/{run_id}")
    status = read_json(run_dir / "status.json")
    for row in status.get("agents", []):
        if Path(row["worktree"]).exists():
            git(root, "worktree", "remove", "--force", row["worktree"])
        subprocess.run(["git", "-C", str(root), "branch", "-D", row["branch"]], capture_output=True)
    return f"removed worktrees and branches of run {run_id}"


def to_json(value):
    return json.dumps(value, indent=2)
