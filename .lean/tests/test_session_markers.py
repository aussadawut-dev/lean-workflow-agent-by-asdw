"""Refusal markers are per session: two sessions in one checkout never share a Stop count (H10)."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ".claude/hooks/quality-gate.sh"
SCRIPTS = (".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py", ".lean/scripts/gate_lock.py",
           ".lean/scripts/gate_mode.py", ".lean/scripts/lean_core.py", ".lean/scripts/contract_guard.py",
           HOOK, ".claude/hooks/session-start.sh", ".gitignore")
BUSY = "Quality Gate busy"
spec = importlib.util.spec_from_file_location("lean_core_under_test", ROOT / ".lean/scripts/lean_core.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def key(session):
    return core.session_key(session)


def reap_fixture(root):
    """Kill any process still running from the fixture dir (a gate holder, its guardian or gate child detach into
    their own session, so a subprocess timeout would orphan them). Matches only commands naming this temp root."""
    import signal
    marker = str(root)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        found = []
        listing = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL).stdout
        for line in listing.splitlines():
            pid, _, command = line.strip().partition(" ")
            if pid.isdigit() and int(pid) != os.getpid() and marker in command:
                found.append(int(pid))
        for pid in found:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        if not found:
            return
        time.sleep(0.5)


class Lock:
    """Hold or release the gate lock the way another running gate would."""

    def __init__(self, root):
        self.path = root / ".agent-runtime/quality-gate.lock"
        self.path.parent.mkdir(exist_ok=True)
        self.handle = None

    def hold(self):
        self.handle = self.path.open("w")
        fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def release(self):
        if self.handle:
            self.handle.close()
            self.handle = None


class ClaudeBase(unittest.TestCase):
    """The real Claude wrapper and runner in a copied Git checkout; the gate passes only with pass.flag."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="lean session markers ")
        self.addCleanup(tmp.cleanup)
        self.root = root = Path(tmp.name)
        self.addCleanup(reap_fixture, root)
        for name in SCRIPTS:
            if (ROOT / name).exists():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, root / name)
        (root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\ntest -f pass.flag\n```\n<!-- gate:end -->\n")
        (root / ".claude/settings.json").write_text("{}")
        git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True, stdin=subprocess.DEVNULL)
        subprocess.run([*git, "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run([*git, "commit", "-qm", "init"], check=True, capture_output=True, stdin=subprocess.DEVNULL)
        accepted = subprocess.run(["python3", str(root / ".lean/scripts/gate_evidence.py"), "--root", str(root),
                                   "accept-controls", "--reason", "Fixture"], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.n = 0
        self.lock = Lock(root)
        self.addCleanup(self.lock.release)

    def run_hook(self, payload, *args):
        return subprocess.run(["bash", str(self.root / HOOK), *args], input=json.dumps(payload), text=True,
                              capture_output=True, timeout=60,
                              env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_GATE_FORCE": "1"})

    def stop(self, session, continued, change=True):
        """One real Stop; returns block, release or pass. A changed state keeps 'nothing changed' out of the way."""
        if change:
            self.n += 1
            (self.root / "w.txt").write_text(f"{self.n}\n")
        payload = {"stop_hook_active": continued}
        if session is not None:
            payload["session_id"] = session
        done = self.run_hook(payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        if not done.stdout.strip():
            return "pass"
        data = json.loads(done.stdout)
        if data.get("decision") == "block":
            return "block"
        self.assertIn("UNVERIFIED", data["systemMessage"])
        return "release"

    def failed(self, session=None):
        path = self.root / (f".agent-runtime/gate-failed.{key(session)}" if session else ".claude/.gate-failed")
        return path.read_text() if path.exists() else None

    def refusal(self, session=None):
        path = self.root / (".agent-runtime/gate-refusal" + (f".{key(session)}" if session else ""))
        return path.exists()


class ClaudeSessionTests(ClaudeBase):
    def test_second_session_continued_first_stop_gets_its_own_three_blocks(self):
        self.assertEqual([self.stop("A", False), self.stop("A", True)], ["block", "block"])
        self.assertEqual(self.failed("A"), "2")
        self.assertEqual([self.stop("B", True) for _ in range(4)], ["block", "block", "block", "release"])
        self.assertEqual([self.stop("A", True), self.stop("A", True)], ["block", "release"])

    def test_alternating_continued_stops_each_get_three_blocks(self):
        outcomes = {"A": [], "B": []}
        for round_ in range(4):
            for session in ("A", "B"):
                outcomes[session].append(self.stop(session, round_ > 0))
        for session in ("A", "B"):
            self.assertEqual(outcomes[session], ["block", "block", "block", "release"], session)

    def test_busy_blocks_of_one_session_survive_another_sessions_refusals(self):
        self.lock.hold()
        self.assertEqual(self.stop("A", False), "block")
        outcomes = []
        for _ in range(3):
            self.lock.release()
            self.assertEqual(self.stop("B", False), "block")  # a real refusal of B in between
            self.lock.hold()
            outcomes.append(self.stop("A", True))
        self.assertEqual(outcomes, ["block", "block", "release"])
        self.assertEqual(self.failed("B"), "1")

    def test_pass_of_one_session_keeps_the_other_counter(self):
        self.stop("A", False)
        self.stop("B", False)
        self.stop("B", True)
        self.assertEqual(self.failed("B"), "2")
        (self.root / "pass.flag").write_text("")
        self.assertEqual(self.stop("A", False), "pass")
        self.assertIsNone(self.failed("A"))
        self.assertEqual(self.failed("B"), "2")
        (self.root / "pass.flag").unlink()
        self.assertEqual(self.stop("B", True), "block")  # B's third
        self.assertEqual(self.stop("B", True), "release")

    def test_seed_of_one_session_neither_clears_nor_is_blocked_by_another(self):
        self.stop("A", False)
        self.stop("A", True)
        before = self.failed("A")
        before_refusal = self.refusal("A")
        baseline = self.root / ".agent-runtime/gate-baseline"
        baseline.unlink(missing_ok=True)
        done = self.run_hook({"session_id": "B"}, "--seed")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.failed("A"), before)
        self.assertEqual(self.refusal("A"), before_refusal)
        self.assertTrue(baseline.exists(), "B's seed must write its baseline despite A's marker")
        self.assertEqual(self.stop("A", True), "block")  # A's third, undisturbed
        self.assertEqual(self.stop("A", True), "release")

    def test_no_session_runs_keep_the_legacy_names_and_behaviour(self):
        outcomes = [self.stop(None, index > 0) for index in range(5)]
        self.assertEqual(outcomes, ["block", "block", "block", "release", "release"])
        self.assertEqual(self.failed(), "5")
        keyed = [p.name for p in (self.root / ".claude").glob(".gate-failed.*")]
        keyed += [p.name for p in (self.root / ".agent-runtime").glob("gate-failed.*")]
        self.assertEqual(keyed, [])
        self.assertEqual(self.stop(None, True, change=False), "release")  # nothing changed: released at once

    def test_legacy_markers_are_ignored_by_a_session_and_dropped_once(self):
        (self.root / ".claude/.gate-failed").write_text("3")
        (self.root / ".agent-runtime").mkdir(exist_ok=True)
        (self.root / ".agent-runtime/gate-refusal").write_text("old")
        self.assertEqual(self.stop("A", True), "block")  # counts from its own marker, not the legacy 3
        self.assertEqual(self.failed("A"), "1")
        (self.root / "pass.flag").write_text("")
        self.assertEqual(self.stop("A", True), "pass")
        self.assertIsNone(self.failed())
        self.assertFalse((self.root / ".agent-runtime/gate-refusal").exists())

    def test_seed_prunes_only_stale_keyed_markers(self):
        old = time.time() - 3 * 86400
        claude, runtime = self.root / ".claude", self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        stale = [runtime / f"gate-failed.{key('old')}", runtime / f"gate-refusal.{key('old')}",
                 claude / f".gate-failed.{key('old')}"]  # the last: an earlier draft's location
        fresh = [runtime / f"gate-failed.{key('new')}", runtime / f"gate-refusal.{key('new')}"]
        other = [claude / ".gate-failed.backup", runtime / "gate-failed.backup", runtime / ("gate-failed." + "a" * 17)]
        for path in stale + fresh + other:
            path.write_text("1")
        for path in stale + other:
            os.utime(path, (old, old))
        done = self.run_hook({"session_id": "C"}, "--seed")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([p.exists() for p in stale], [False] * 3)
        self.assertEqual([p.exists() for p in fresh], [True, True])
        self.assertTrue(all(p.exists() for p in other))


class RelocatedMarkerTests(ClaudeBase):
    """The keyed failed marker lives under .agent-runtime, so a project whose .gitignore is still the v4 file
    (no `.claude/.gate-failed.*` glob) sees no new untracked path and the 'nothing changed' release holds."""

    V4_IGNORE = ".env\n.claude/settings.local.json\n.claude/.gate-cache\n.claude/.gate-failed\n.agent-runtime/\n__pycache__/\n*.pyc\n"

    def setUp(self):
        super().setUp()
        git = ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        (self.root / ".gitignore").write_text(self.V4_IGNORE)
        subprocess.run([*git, "commit", "-qam", "v4 ignore"], check=True, capture_output=True, stdin=subprocess.DEVNULL)

    def porcelain(self):
        return subprocess.run(["git", "-C", str(self.root), "status", "--porcelain", "--untracked-files=all"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout

    def gate_state(self):
        return subprocess.run(["python3", str(self.root / ".lean/scripts/gate_evidence.py"), "--root", str(self.root),
                               "gate-state"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout

    def test_a_refusal_with_a_session_id_adds_no_untracked_path_and_keeps_the_state(self):
        (self.root / "w.txt").write_text("work\n")
        before = (self.porcelain(), self.gate_state())
        self.assertEqual(self.stop("A", False, change=False), "block")
        self.assertTrue((self.root / f".agent-runtime/gate-failed.{key('A')}").is_file())
        self.assertEqual((self.porcelain(), self.gate_state()), before)
        self.assertEqual(self.stop("A", True, change=False), "release")  # still 'nothing changed'
        self.assertEqual((self.porcelain(), self.gate_state()), before)

    def test_a_busy_refusal_leaves_no_untracked_path_either(self):
        (self.root / "w.txt").write_text("work\n")
        before = (self.porcelain(), self.gate_state())
        self.lock.hold()
        self.assertEqual(self.stop("A", False, change=False), "block")
        self.assertEqual(self.failed("A"), "1")
        self.assertEqual((self.porcelain(), self.gate_state()), before)

    def test_a_keyed_file_at_the_previous_location_is_dropped_once_on_seed_and_pass(self):
        old = self.root / f".claude/.gate-failed.{key('A')}"
        old.write_text("3")
        done = self.run_hook({"session_id": "A"}, "--seed")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(old.exists())
        old.write_text("3")
        (self.root / "pass.flag").write_text("")
        self.assertEqual(self.stop("A", False), "pass")
        self.assertFalse(old.exists())

    def test_status_readers_see_the_keyed_marker_in_both_locations(self):
        sys.path.insert(0, str(ROOT / ".lean/scripts"))
        import workflow
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        old = self.root / f".claude/.gate-failed.{key('A')}"
        old.write_text("2")
        self.assertEqual(workflow.gate_status(self.root), "FAIL")
        new = runtime / f"gate-failed.{key('B')}"
        new.write_text("c1")
        os.utime(old, (time.time() - 100, time.time() - 100))
        self.assertEqual(workflow.gate_status(self.root), "CONTRACT_REFUSED")


class CodexBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="lean session codex ")
        self.addCleanup(tmp.cleanup)
        self.root = root = Path(tmp.name)
        self.addCleanup(reap_fixture, root)
        git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True, stdin=subprocess.DEVNULL)
        (root / "seed.txt").write_text("seed\n")
        shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
        for src in (".lean/scripts", ".codex/hooks"):
            shutil.copytree(ROOT / src, root / src, ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run([*git, "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run([*git, "commit", "-qm", "init"], check=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.runtime = root / ".agent-runtime"
        self.runtime.mkdir(exist_ok=True)
        self.n = 0
        self.lock = Lock(root)
        self.addCleanup(self.lock.release)

    def hook(self, event, payload):
        done = subprocess.run([sys.executable, str(self.root / ".codex/hooks/quality_gate.py"), event,
                               "--root", str(self.root)], input=json.dumps(payload), text=True,
                              capture_output=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout) if done.stdout.strip() else {}

    def stop(self, session, continued, change=True, commit=False):
        if change or commit:
            self.n += 1
            (self.root / "w.txt").write_text(f"{self.n}\n")
        if commit:  # new shipping state, clean tree: the Stop is a gate refusal, not a contract one
            git = ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run([*git, "add", "."], check=True, stdin=subprocess.DEVNULL)
            subprocess.run([*git, "commit", "-qm", f"c{self.n}"], check=True, capture_output=True,
                           stdin=subprocess.DEVNULL)
        out = self.hook("stop", {"stop_hook_active": continued, "session_id": session})
        if out.get("decision") == "block":
            return "block"
        self.assertIn("UNVERIFIED", out["systemMessage"])
        return "release"

    def failed(self, session):
        path = self.runtime / f"codex-gate-failed.{key(session)}"
        return path.read_text() if path.exists() else None


class CodexSessionTests(CodexBase):
    def test_second_session_continued_first_stop_gets_its_own_three_blocks(self):
        self.stop("A", False)
        self.stop("A", True)
        self.assertEqual([self.stop("B", True) for _ in range(4)], ["block", "block", "block", "release"])
        self.assertEqual([self.stop("A", True), self.stop("A", True)], ["block", "release"])

    def test_alternating_continued_stops_each_get_three_blocks(self):
        outcomes = {"A": [], "B": []}
        for round_ in range(4):
            for session in ("A", "B"):
                outcomes[session].append(self.stop(session, round_ > 0))
        for session in ("A", "B"):
            self.assertEqual(outcomes[session], ["block", "block", "block", "release"], session)

    def test_busy_blocks_survive_the_other_sessions_refusals(self):
        self.lock.hold()
        self.assertEqual(self.stop("A", False, change=False), "block")
        outcomes = []
        for _ in range(3):
            self.lock.release()
            self.assertEqual(self.stop("B", False, change=False, commit=True), "block")
            self.lock.hold()
            outcomes.append(self.stop("A", True, change=False))
        self.assertEqual(outcomes, ["block", "block", "release"])
        self.assertEqual(self.failed("B"), "1")

    def test_session_start_prunes_stale_keyed_markers_and_keeps_legacy_ones_for_no_session(self):
        old = time.time() - 3 * 86400
        stale = self.runtime / f"codex-gate-refusal.{key('old')}"
        fresh = self.runtime / f"codex-gate-failed.{key('new')}"
        stale.write_text("x")
        fresh.write_text("1")
        os.utime(stale, (old, old))
        self.hook("session-start", {"session_id": "C"})
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())

    def test_no_session_uses_the_legacy_names(self):
        done = subprocess.run([sys.executable, str(self.root / ".codex/hooks/quality_gate.py"), "stop",
                               "--root", str(self.root)], input=json.dumps({"stop_hook_active": False}),
                              text=True, capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((self.runtime / "codex-gate-failed").read_text(), "1")
        self.assertEqual(list(self.runtime.glob("codex-gate-failed.*")), [])


BAD_KEYS = ("../../../escape", "AAAAAAAAAAAAAAAA", "a" * 15, "a" * 17, 1234567890123456, None, "")


class UnusableMarkerClaudeTests(ClaudeBase):
    """A marker that cannot be kept must bound a continued Stop: release UNVERIFIED, never block without end."""

    def runtime_as_file(self):
        shutil.rmtree(self.root / ".agent-runtime", ignore_errors=True)
        (self.root / ".agent-runtime").write_text("not a directory")

    def stops(self, session, count):
        return [self.stop(session, index > 0) for index in range(count)]

    def test_keyed_marker_that_is_a_directory_blocks_once_then_releases(self):
        (self.root / ".agent-runtime").mkdir(exist_ok=True)
        (self.root / f".agent-runtime/gate-failed.{key('A')}").mkdir()
        self.assertEqual(self.stops("A", 4), ["block", "release", "release", "release"])
        self.assertEqual(self.stop("A", False), "block")  # a fresh Stop blocks once again

    def test_legacy_marker_that_is_a_directory_blocks_once_then_releases(self):
        (self.root / ".claude/.gate-failed").mkdir()
        self.assertEqual(self.stops(None, 4), ["block", "release", "release", "release"])

    def test_marker_that_is_a_fifo_never_hangs(self):
        (self.root / ".agent-runtime").mkdir(exist_ok=True)
        os.mkfifo(self.root / f".agent-runtime/gate-failed.{key('A')}")
        self.assertEqual(self.stops("A", 3), ["block", "release", "release"])

    def test_unreadable_runtime_marker_noise_stays_out_of_the_reason(self):
        (self.root / ".agent-runtime").mkdir(exist_ok=True)
        (self.root / f".agent-runtime/gate-failed.{key('A')}").mkdir()
        done = self.run_hook({"stop_hook_active": False, "session_id": "A"})
        self.assertNotIn("Is a directory", json.loads(done.stdout)["reason"])

    def test_runtime_that_is_a_regular_file_keeps_the_cap_of_three_in_claude(self):
        self.runtime_as_file()
        self.assertEqual(self.stops("A", 5), ["block"] * 3 + ["release"] * 2)
        self.assertEqual((self.root / ".claude/.gate-failed").read_text(), "5")
        self.assertEqual(self.stop("A", False), "block")
        self.assertEqual((self.root / ".claude/.gate-failed").read_text(), "1")

    def test_read_only_runtime_keeps_the_cap_of_three_in_claude(self):
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        runtime.chmod(0o500)
        self.addCleanup(runtime.chmod, 0o700)
        self.assertEqual(self.stops("A", 5), ["block"] * 3 + ["release"] * 2)

    def test_no_marker_can_be_kept_releases_a_continued_stop(self):
        self.runtime_as_file()
        (self.root / ".claude/.gate-failed").mkdir()
        self.assertEqual(self.stops("A", 3), ["block", "release", "release"])

    def test_a_pass_clears_the_fallback_count(self):
        self.runtime_as_file()
        self.stops("A", 2)
        self.assertEqual((self.root / ".claude/.gate-failed").read_text(), "2")
        (self.root / ".agent-runtime").unlink()  # the directory comes back (and the controls are accepted again)
        accepted = subprocess.run(["python3", str(self.root / ".lean/scripts/gate_evidence.py"), "--root", str(self.root),
                                   "accept-controls", "--reason", "Fixture"], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        (self.root / "pass.flag").write_text("")
        self.assertEqual(self.stop("A", True), "pass")
        self.assertFalse((self.root / ".claude/.gate-failed").exists())


class MalformedSessionClaudeTests(ClaudeBase):
    """A malformed session id keeps its message but is counted under the legacy marker, so it is bounded."""

    BAD = ("a\nb", 5, None, ["x"], {"k": 1}, True)

    def payload_stop(self, session, continued):
        self.n += 1
        (self.root / "w.txt").write_text(f"{self.n}\n")
        done = self.run_hook({"stop_hook_active": continued, "session_id": session})
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        if data.get("decision") == "block":
            return "block", data["reason"]
        self.assertIn("UNVERIFIED", data["systemMessage"])
        return "release", data["systemMessage"]

    def test_repeated_stops_block_three_times_then_release(self):
        for bad in self.BAD:
            with self.subTest(session=bad):
                self.setUp()
                results = [self.payload_stop(bad, index > 0) for index in range(6)]
                self.assertEqual([kind for kind, _ in results], ["block"] * 3 + ["release"] * 3, results)
                for kind, text in results[:3]:
                    self.assertEqual(text.strip(), "Gate evidence: session_id must be a single-line string")
                self.assertEqual((self.root / ".claude/.gate-failed").read_text(), "c6")
                self.assertEqual(self.payload_stop(bad, False)[0], "block")  # a fresh Stop blocks again
                self.assertEqual((self.root / ".claude/.gate-failed").read_text(), "c1")

    def test_a_well_formed_session_is_not_counted_with_it(self):
        for index in range(2):
            self.payload_stop("a\nb", index > 0)
        self.assertEqual(self.stop("A", False), "block")
        self.assertEqual(self.failed("A"), "1")

    def test_a_malformed_stop_never_passes_and_writes_no_pass_record(self):
        (self.root / "pass.flag").write_text("")
        results = [self.payload_stop("a\nb", index > 0)[0] for index in range(5)]
        self.assertEqual(results, ["block"] * 3 + ["release"] * 2)
        self.assertFalse((self.root / ".claude/.gate-cache").exists())


def files_under(root):
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts}


def trap_escape(root):
    """Directories that would let the '../../../escape' key land a file outside the checkout."""
    for name in ("gate-failed...", "codex-gate-failed...", "gate-refusal..."):
        (root / ".agent-runtime" / name).mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(exist_ok=True)
    (root / ".claude/.gate-failed...").mkdir(exist_ok=True)


class BadKeyClaudeTests(ClaudeBase):
    """A corrupted core's session_key must never become a path component: no key means the legacy names."""

    def corrupt(self, value):
        path = self.root / ".lean/scripts/lean_core.py"
        path.write_text(path.read_text() + f"\n\ndef session_key(session):\n    return {value!r}\n")
        accepted = subprocess.run(["python3", str(self.root / ".lean/scripts/gate_evidence.py"), "--root", str(self.root),
                                   "accept-controls", "--reason", "Fixture"], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        trap_escape(self.root)
        self.escape = self.root.parent / "escape"
        self.assertFalse(self.escape.exists())
        return files_under(self.root)

    def check(self, value, busy):
        before = self.corrupt(value)
        if busy:
            self.lock.hold()
        results = [self.stop("sess", False)] + [self.stop("sess", True) for _ in range(4)]
        self.assertEqual(results[0], "block", (value, results))
        self.assertEqual(results[-1], "release", (value, results))
        self.assertFalse(self.escape.exists(), value)
        new = files_under(self.root) - before
        for name in new:
            self.assertTrue(name.startswith((".agent-runtime/", ".claude/")) or name == "w.txt", (value, name))
        self.assertTrue(all(not n.startswith(".agent-runtime/gate-failed.") and "escape" not in n for n in new),
                        (value, new))
        self.assertTrue((self.root / ".claude/.gate-failed").exists(), (value, new))  # the legacy name

    def test_runner_path_ignores_an_invalid_key(self):
        for value in BAD_KEYS:
            with self.subTest(key=value):
                self.setUp()
                self.check(value, busy=False)

    def test_busy_path_ignores_an_invalid_key(self):
        for value in BAD_KEYS:
            with self.subTest(key=value):
                self.setUp()
                self.check(value, busy=True)


class BadKeyCodexTests(CodexBase):
    def test_codex_ignores_an_invalid_key(self):
        for value in BAD_KEYS:
            with self.subTest(key=value):
                self.setUp()
                path = self.root / ".lean/scripts/lean_core.py"
                path.write_text(path.read_text() + f"\n\ndef session_key(session):\n    return {value!r}\n")
                trap_escape(self.root)
                escape = self.root.parent / "escape"
                self.assertFalse(escape.exists())
                before = files_under(self.root)
                results = [self.stop("sess", False)] + [self.stop("sess", True) for _ in range(4)]
                self.assertEqual((results[0], results[-1]), ("block", "release"), (value, results))
                self.assertFalse(escape.exists(), value)
                new = files_under(self.root) - before
                self.assertTrue(all(n.startswith(".agent-runtime/") or n == "w.txt" for n in new), (value, new))
                self.assertTrue((self.runtime / "codex-gate-failed").exists(), (value, new))
                self.assertEqual([n for n in new if "escape" in n or "failed." in n], [], (value, new))


class SessionKeyTests(unittest.TestCase):
    def test_properties(self):
        first = core.session_key("session-1")
        self.assertRegex(first, r"^[0-9a-f]{16}$")
        self.assertEqual(first, core.session_key("session-1"))
        self.assertNotEqual(first, core.session_key("session-2"))
        self.assertNotIn("session", first)
        for none in ("", None, 3, b"x", ["a"]):
            self.assertIsNone(core.session_key(none), none)
        self.assertRegex(core.session_key("päth/ with spaces\t"), r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
