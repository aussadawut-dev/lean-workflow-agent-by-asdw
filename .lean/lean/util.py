"""Shared helpers: workflow root, symlink-safe paths, atomic JSON, locks and Git."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile

# .lean/lean/util.py -> repository root.
WORKFLOW_ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ".agent-runtime"


class LeanError(ValueError):
    """A refusal the CLI reports as a message, never a traceback."""


def safe_path(root, relative):
    """root/relative, refusing any symlink on the way so records stay inside the checkout."""
    path = Path(root)
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise LeanError(f"path must not cross a symlink: {path}")
    return path


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LeanError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    """Strict JSON: duplicate keys are an error, not a silent last-wins."""
    with open(path) as source:
        return json.load(source, object_pairs_hook=unique_keys)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2) + "\n")


def write_text(path, text):
    """Atomic replace through a synced temporary file in the same directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o7777 if path.is_file() else 0o666 & ~current_umask()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, prefix=f".{path.name}.") as out:
            temporary = Path(out.name)
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, mode)  # NamedTemporaryFile creates 0600.
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def current_umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def runtime(root, create=True):
    """The ignored per-checkout runtime directory."""
    path = safe_path(root, RUNTIME)
    if create:
        path.mkdir(exist_ok=True)
    return path


@contextlib.contextmanager
def locked(root, name, blocking=True):
    """An exclusive flock on .agent-runtime/<name>; raises BlockingIOError when busy and non-blocking."""
    path = safe_path(runtime(root), name)
    with path.open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield


def git(root, *args, check=True):
    """Git stdout as bytes; raises CalledProcessError when check and Git fails."""
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if check and result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    return result.stdout


def in_git(root):
    return subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                          capture_output=True).returncode == 0


def head(root):
    """HEAD's commit id, or "" before the first commit."""
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD"],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""
