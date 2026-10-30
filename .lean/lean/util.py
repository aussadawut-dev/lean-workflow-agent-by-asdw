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


def recorded_gate(root):
    """The gate runner's last recorded result from its markers alone, importing none of the gate:
    CONTRACT_REFUSED, FAIL, LAST_PASS or NOT_RUN (status bars call this on every refresh)."""
    folder = Path(root) / RUNTIME
    try:
        result = read_json(safe_path(root, RUNTIME + "/gate-result.json"))
        if (not isinstance(result, dict) or result.get("schema") != 1
                or result.get("status") not in ("PASS", "FAIL", "CONTRACT_REFUSED", "UNVERIFIED", "RUNNING")):
            return "UNKNOWN"
        return "LAST_PASS" if result["status"] == "PASS" else result["status"]
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        return "UNKNOWN"
    failed = folder / "gate-failed"
    if failed.is_file():
        # A "c" marker is a contract refusal, which says nothing about the checks.
        return "CONTRACT_REFUSED" if failed.read_text().startswith("c") else "FAIL"
    return "LAST_PASS" if (folder / "gate-cache").is_file() else "NOT_RUN"


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
    return GitView(root).in_git()


def head(root):
    """HEAD's commit id, or "" before the first commit."""
    return GitView(root).head()


class GitView:
    """Read-only Git answers for one root, each fetched once and shared by its callers.

    Use one view only within a window in which nothing writes the repository (no gate command,
    commit or checkout runs in between); a fresh view queries Git again. Each answer is exactly
    what its separate Git call returns:

    - `rev-parse --is-inside-work-tree -q --verify HEAD` prints "true" or "false" exactly when
      `--is-inside-work-tree` alone succeeds, then HEAD's id exactly when `-q --verify HEAD` does.
    - `ls-files -t --stage --cached --others` tags each record: "? " marks an untracked path, any
      other tag precedes the record `ls-files --stage` prints, in the same order.
    """
    _CACHED_TAGS = (b"H ", b"S ", b"M ")  # Cached, skip-worktree and unmerged entries.

    def __init__(self, root):
        self.root = root
        self._probe = None
        self._listing = None
        self._others = None

    def _run(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True)

    def _probed(self):
        if self._probe is None:
            result = self._run("rev-parse", "--is-inside-work-tree", "-q", "--verify", "HEAD")
            lines = result.stdout.split(b"\n")
            inside = lines[0] in (b"true", b"false")
            commit = lines[1].decode().strip() if inside and result.returncode == 0 and len(lines) > 1 else ""
            self._probe = (inside, commit)
        return self._probe

    def in_git(self):
        """Whether `git rev-parse --is-inside-work-tree` succeeds here."""
        return self._probed()[0]

    def head(self):
        """What `git rev-parse -q --verify HEAD` prints when it succeeds, else ""."""
        return self._probed()[1]

    def head_text(self):
        """The stripped stdout of `git rev-parse HEAD`, whether or not it succeeds."""
        # With a verified HEAD it prints the same id; otherwise (unborn, not a repository) ask it.
        return self.head() or self._run("rev-parse", "HEAD").stdout.decode().strip()

    def _listed(self):
        if self._listing is None:
            out = git(self.root, "ls-files", "-t", "--stage", "--cached", "--others", "--exclude-standard", "-z")
            stage, others = [], []
            records = out.split(b"\0")
            for record in records[:-1] if not records[-1] else [b"unterminated"]:
                tag, rest = record[:2], record[2:]
                if tag == b"? " and rest:
                    others.append(rest)
                elif tag in self._CACHED_TAGS and b"\t" in rest:
                    stage.append(rest)
                else:  # Never guess at an unknown record: keep the defining calls instead.
                    self._listing = False
                    return None
            self._listing = (b"".join(record + b"\0" for record in stage),
                             {record.split(b"\t", 1)[1] for record in stage}, set(others))
        return self._listing or None

    def stage(self):
        """The stdout of `git ls-files --stage -z`."""
        listed = self._listed()
        return listed[0] if listed else git(self.root, "ls-files", "--stage", "-z")

    def visible(self):
        """The names `git ls-files --cached --others --exclude-standard -z` prints."""
        listed = self._listed()
        if listed:
            return listed[1] | listed[2]
        return set(git(self.root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""}

    def others(self):
        """The names `git ls-files --others --exclude-standard -z` prints."""
        if self._others is None:
            # Reuse a listing already fetched; otherwise one plain call costs no more than listing.
            self._others = self._listing[2] if self._listing else set(
                git(self.root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""}
        return self._others
