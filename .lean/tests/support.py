"""Shared test helpers: install this workflow into disposable Git checkouts and run `lean` there."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".lean"))
LEAN = ".lean/bin/lean"
# The workflow code and both providers' hook wiring.
RUNTIME_FILES = (".gitignore", ".claude/settings.json", ".codex/hooks.json", LEAN)
# Fixtures live in throwaway directories; `lean test` already keeps their bytecode out of the user's
# cache, and so does a test file run on its own (every lean process a test starts inherits this).
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def install(root, extra=()):
    """Copy the lean CLI, its package and hook configuration into `root`."""
    root = Path(root)
    for name in RUNTIME_FILES + tuple(extra):
        source = ROOT / name
        if source.exists():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    shutil.copytree(ROOT / ".lean/lean", root / ".lean/lean", ignore=shutil.ignore_patterns("__pycache__"),
                    dirs_exist_ok=True)


def lean(root, *args, input=None, env=None, cwd=None):
    """Run the installed CLI of `root` against `root`."""
    return subprocess.run([sys.executable, str(Path(root) / LEAN), "--root", str(root), *args], input=input,
                          text=True, capture_output=True, env=env, cwd=cwd or root)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def commit(root, message="fixture"):
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", message, "--allow-empty"], check=True)


def configured(root, provider, event):
    """The command a provider's hook configuration runs for an event."""
    name = ".claude/settings.json" if provider == "claude" else ".codex/hooks.json"
    return json.loads((Path(root) / name).read_text())["hooks"][event][0]["hooks"][0]["command"]


def run_hook(root, provider, event, payload, extra_env=None):
    """Run a hook exactly as the provider's configured command does."""
    environment = dict(os.environ)
    environment.pop("LEAN_GATE_FORCE", None)
    environment.pop("LEAN_GATE_LOCK_FD", None)
    if provider == "claude":
        environment["CLAUDE_PROJECT_DIR"] = str(root)
    environment.update(extra_env or {})
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(["sh", "-c", configured(root, provider, event)], cwd=root, env=environment, input=stdin,
                          text=True, capture_output=True)


def stop_refusal(result):
    """Stops refuse with a JSON decision block on exit 0; read it as exit 2 + reason."""
    try:
        data = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else None
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("decision") == "block":
        return subprocess.CompletedProcess(result.args, 2, "", result.stderr + data["reason"])
    return result


# Files a project creates at setup, beside the registered release.
def structure_references(text):
    """The workflow paths a document names, as `lean lint` finds them."""
    from lean import structure
    return structure.references(text)


PROJECT_FILES = (".lean/PROJECT.md", ".lean/models.json", ".lean/config.json", ".gitignore")


def install_release(root, init=True, source=ROOT):
    """Copy exactly the registered release plus setup's project files, with the skill discovery links.

    The project files come from the installation running the tests, so the project-owned files they
    name (a PROJECT.md naming `.lean/LOCAL-EXTENSIONS.md`) come along; nothing else of the project does."""
    root, source = Path(root), Path(source)
    registry = json.loads((source / ".lean/assets.json").read_text())
    copied = registry["files"] + list(PROJECT_FILES)
    for name in copied:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    pending = [reference for name in copied if name.endswith(".md")
               for reference in structure_references((source / name).read_text())]
    while pending:
        name = pending.pop()
        if (root / name).exists() or not (source / name).is_file():
            continue  # A reference to a missing file is lint's to report.
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, root / name)
        if name.endswith(".md"):
            pending += structure_references((source / name).read_text())
    for tree in (".claude/skills", ".agents/skills"):
        (root / tree).mkdir(parents=True, exist_ok=True)
        for skill in registry["skills"]:
            os.symlink(f"../../.lean/skills/{skill}", root / tree / skill)
    if init:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
