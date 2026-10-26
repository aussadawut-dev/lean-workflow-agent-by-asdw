"""Partial upgrade: a project that has only SOME of the v5 gate files must degrade or refuse, never pass.

Each case builds a throwaway Git repository from copies of the working-tree files, swaps some of them for an
older version (git show 9b6252d:...) or removes them, selects the failing gate `false`, accepts those controls,
and drives a Stop through the Claude wrapper (.claude/hooks/quality-gate.sh) and/or the Codex hook.
The safe property: a failing gate never yields a pass (exit 0 with no block and no UNVERIFIED release).
Set LEAN_MATRIX=1 to print every observed (combination -> exit, decision, markers) line.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "9b6252d"
HAVE_BASELINE = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", BASELINE + "^{commit}"],
                               capture_output=True, stdin=subprocess.DEVNULL).returncode == 0
NEEDS_BASELINE = unittest.skipUnless(HAVE_BASELINE, f"baseline commit {BASELINE} (v4.17.0) not in this clone")

CORE = ".lean/scripts/lean_core.py"
LOCK = ".lean/scripts/gate_lock.py"
RUNNER = ".lean/scripts/quality-gate.sh"
WRAPPER = ".claude/hooks/quality-gate.sh"
CODEX = ".codex/hooks/quality_gate.py"
SCRIPT_GLOBS = (".lean/scripts/*.py", ".lean/scripts/*.sh", ".claude/hooks/*.sh", ".codex/hooks/quality_gate.py",
                ".codex/hooks.json", ".codex/quality-gate.json", ".gitignore")


def baseline(name):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{name}"], capture_output=True, check=True,
                          stdin=subprocess.DEVNULL).stdout


# A core whose gate_refusal/session_key are missing: the file exists and imports, the newer call fails.
OLD_CORE_NO_GATE_REFUSAL = b"BLOCK = 'block'\nRELEASE_UNCHANGED = 'release_unchanged'\nRELEASE_CAPPED = 'release_capped'\n"
# A core that raises while importing.
BROKEN_CORE = b"raise RuntimeError('half-written core')\n"

MATRIX = []


def verdict(code, out):
    """block | block-exit2 | release (UNVERIFIED) | PASS. PASS on a failing gate is the unsafe outcome."""
    if code == 2:
        return "block-exit2"
    try:
        data = json.loads(out) if out.strip() else {}
    except ValueError:
        return "PASS" if code == 0 else f"exit{code}"
    if data.get("decision") == "block":
        return "block"
    if "UNVERIFIED" in data.get("systemMessage", ""):
        return "release"
    return "PASS" if code == 0 else f"exit{code}"


class Fixture:
    def __init__(self, test, overrides=None, label=""):
        self.label = label
        tmp = tempfile.TemporaryDirectory(prefix="lean partial ")
        test.addCleanup(tmp.cleanup)
        self.root = root = Path(tmp.name)
        for pattern in SCRIPT_GLOBS:
            for path in sorted(ROOT.glob(pattern)):
                target = root / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        (root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        (root / ".claude/settings.json").write_text("{}")
        for name, value in (overrides or {}).items():
            if value is None:
                (root / name).unlink()
            else:
                (root / name).write_bytes(value)
                (root / name).chmod(0o755)
        git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "init"]):
            subprocess.run([*git, *args], check=True, capture_output=True, stdin=subprocess.DEVNULL)
        accepted = subprocess.run(["python3", str(root / ".lean/scripts/gate_evidence.py"), "--root", str(root),
                                   "accept-controls", "--reason", "Fixture selects a failing gate"],
                                  capture_output=True, text=True, stdin=subprocess.DEVNULL)
        test.assertEqual(accepted.returncode, 0, accepted.stderr)

    def env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LEAN_GATE", "CLAUDE_"))}
        env["CLAUDE_PROJECT_DIR"] = str(self.root)
        return env

    def markers(self):
        """Refusal markers by base name. A runner may suffix the file per session (.gate-failed.<key>) or not
        (v4.17.0); both are read, so the property does not depend on the marker naming of either generation."""
        out = {}
        for pattern in (".claude/.gate-failed*", ".agent-runtime/codex-gate-failed*"):
            for path in sorted(self.root.glob(pattern)):
                if path.is_file():
                    out[path.name.split(".gate-failed")[0] + ".gate-failed" if path.parent.name == ".claude"
                        else "codex-gate-failed"] = path.read_text()
        return out

    def claude(self, continued=False, session="s1", runner=False):
        payload = {"stop_hook_active": continued, "session_id": session}
        if runner:
            argv = ["bash", str(self.root / RUNNER), "--root", str(self.root), "--claude-hook"]
        else:
            argv = ["bash", str(self.root / WRAPPER), "--claude-hook"]
        result = subprocess.run(argv, input=json.dumps(payload), text=True, capture_output=True, env=self.env(),
                                cwd=self.root, timeout=60)
        return self.record("claude-runner" if runner else "claude", continued, result)

    def codex(self, continued=False, session="s1"):
        payload = {"stop_hook_active": continued, "session_id": session}
        result = subprocess.run(["python3", str(self.root / CODEX), "stop"], input=json.dumps(payload), text=True,
                                capture_output=True, env=self.env(), cwd=self.root, timeout=60)
        return self.record("codex", continued, result)

    def record(self, entry, continued, result):
        seen = verdict(result.returncode, result.stdout)
        step = {"entry": entry, "continued": continued, "exit": result.returncode, "verdict": seen,
                "markers": self.markers(), "stdout": result.stdout, "stderr": result.stderr}
        line = f"{self.label or '-'} | {entry} {'continued' if continued else 'fresh'} | exit={result.returncode} {seen} markers={step['markers']}"
        if "Traceback" in result.stderr:
            line += " TRACEBACK"
        MATRIX.append(line)
        if os.environ.get("LEAN_MATRIX"):
            print("MATRIX " + line, file=sys.stderr)
        return step


class SafeMixin:
    def assertNeverPasses(self, step):
        self.assertNotEqual(step["verdict"], "PASS", step)
        self.assertNotRegex(step["verdict"], r"^exit", step)

    def fixture(self, overrides=None, label=""):
        return Fixture(self, overrides, label)


class CoreAbsentTests(SafeMixin, unittest.TestCase):
    """(a) everything v5 except lean_core.py."""

    def test_claude_shell_fresh_blocks_once_then_continued_releases(self):
        fx = self.fixture({CORE: None}, "a core-absent")
        fresh = fx.claude()
        self.assertEqual(fresh["verdict"], "block", fresh)
        self.assertEqual(fresh["markers"].get(".gate-failed"), "1")  # a session-suffixed marker is read too
        for _ in range(2):  # the fallback never counts: every continued Stop is released
            cont = fx.claude(continued=True)
            self.assertEqual(cont["verdict"], "release", cont)
            self.assertIn("still refused", cont["stdout"])
            self.assertEqual(cont["markers"].get(".gate-failed"), "4")
        self.assertEqual(cont["exit"], 0)

    def test_claude_runner_direct_matches(self):
        fx = self.fixture({CORE: None}, "a core-absent")
        self.assertEqual(fx.claude(runner=True)["verdict"], "block-exit2")
        self.assertEqual(fx.claude(continued=True, runner=True)["verdict"], "release")

    def test_codex_fallback_blocks_once_then_releases(self):
        fx = self.fixture({CORE: None}, "a core-absent")
        fresh = fx.codex()
        self.assertEqual(fresh["verdict"], "block", fresh)
        cont = fx.codex(continued=True)
        self.assertEqual(cont["verdict"], "release", cont)
        self.assertEqual(cont["exit"], 0)
        # Codex: lean_core is None -> OSError -> fallback (no shared count, so a continued Stop is released).

    def test_guard_controls_treats_a_missing_control_as_changed(self):
        # gate_evidence records a missing control as null; deleting lean_core.py AFTER controls were accepted
        # makes the control set differ, so guard-controls refuses (it does not ignore it, nor crash).
        fx = self.fixture(None, "a core-deleted-after-accept")
        (fx.root / CORE).unlink()
        step = fx.claude()
        self.assertEqual(step["verdict"], "block", step)
        self.assertIn("Protected gate controls changed", step["stdout"] + step["stderr"])
        again = subprocess.run(["python3", str(fx.root / ".lean/scripts/gate_evidence.py"), "--root", str(fx.root),
                                "guard-controls"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertNotEqual(again.returncode, 0)
        self.assertNotIn("Traceback", again.stderr)

    def test_core_absent_at_first_record_is_accepted_as_null(self):
        # Core absent when controls were first recorded: guard-controls passes (null == null), and the failing
        # gate is what refuses. Pin: the missing control is not itself an error.
        fx = self.fixture({CORE: None}, "a core-absent")
        data = json.loads((fx.root / ".agent-runtime/gate-controls.json").read_text())
        self.assertIsNone(data["controls"][CORE])
        done = subprocess.run(["python3", str(fx.root / ".lean/scripts/gate_evidence.py"), "--root", str(fx.root),
                               "guard-controls"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)


class OldCoreTests(SafeMixin, unittest.TestCase):
    """(b) lean_core.py present but lacking what the newer hooks call, or failing to import."""

    def check(self, stub, label):
        fx = self.fixture({CORE: stub}, label)
        claude = [fx.claude(), fx.claude(continued=True)]
        for step in claude:
            self.assertNeverPasses(step)
            self.assertNotIn("Traceback", step["stderr"], step)
        self.assertEqual([s["verdict"] for s in claude], ["block", "release"], claude)
        # Claude degrades: the shell falls back when `import lean_core`/`gate_refusal` fails.
        # Codex fails closed too: a core that raises on import or lacks gate_refusal is treated like a missing one
        # (a fresh Stop blocks once, a continued Stop is released UNVERIFIED), never a traceback with empty stdout.
        codex = [fx.codex(), fx.codex(continued=True)]
        for step in codex:
            self.assertNeverPasses(step)
            self.assertEqual(step["exit"], 0, step)
            self.assertNotIn("Traceback", step["stderr"], step)
        self.assertEqual([s["verdict"] for s in codex], ["block", "release"], codex)
        return codex

    def test_core_without_gate_refusal(self):
        self.check(OLD_CORE_NO_GATE_REFUSAL, "b core-without-gate_refusal")

    def test_core_that_raises_on_import(self):
        self.check(BROKEN_CORE, "b core-broken-import")

    def test_core_exiting_zero_at_import(self):
        self.check(b"raise SystemExit(0)\n", "b core-exit0-import")

    def test_core_whose_gate_refusal_exits_zero(self):
        stub = OLD_CORE_NO_GATE_REFUSAL + b"def gate_refusal(p, c, i, s):\n    raise SystemExit(0)\n"
        fx = self.fixture({CORE: stub}, "b core-gate_refusal-exit0")
        codex = [fx.codex(), fx.codex(continued=True)]
        for step in codex:
            self.assertNeverPasses(step)
            self.assertEqual(step["exit"], 0, step)
            self.assertNotEqual(step["stdout"].strip(), "", step)
        self.assertEqual([s["verdict"] for s in codex], ["block", "release"], codex)
        claude = [fx.claude(), fx.claude(continued=True)]
        for step in claude:
            self.assertNeverPasses(step)

    def test_core_whose_gate_refusal_exits_two_is_not_masked(self):
        stub = OLD_CORE_NO_GATE_REFUSAL + b"def gate_refusal(p, c, i, s):\n    raise SystemExit(2)\n"
        fx = self.fixture({CORE: stub}, "b core-gate_refusal-exit2")
        step = fx.codex()
        self.assertEqual((step["exit"], step["stdout"].strip()), (2, ""), step)  # non-zero is not a pass

    def test_core_without_session_key(self):
        stub = (OLD_CORE_NO_GATE_REFUSAL
                + b"def gate_refusal(previous, continued, is_contract, same):\n    return BLOCK, '1'\n")
        fx = self.fixture({CORE: stub}, "b core-without-session_key")
        fresh, cont = fx.codex(), fx.codex(continued=True)
        self.assertEqual((fresh["exit"], fresh["verdict"]), (0, "block"), fresh)
        self.assertEqual((cont["exit"], cont["verdict"]), (0, "block"), cont)  # the core still counts, legacy names
        self.assertNotIn("Traceback", fresh["stderr"] + cont["stderr"])
        self.assertTrue((fx.root / ".agent-runtime/codex-gate-failed").is_file())  # legacy name


@NEEDS_BASELINE
class LockMixTests(SafeMixin, unittest.TestCase):
    """(c)/(d) gate_lock.py and quality-gate.sh from different generations."""

    def hold_lock(self, fx):
        runtime = fx.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        code = ("import fcntl,os,sys,time\nfd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT,0o600)\n"
                "fcntl.flock(fd,fcntl.LOCK_EX)\nprint('held',flush=True)\ntime.sleep(60)\n")
        holder = subprocess.Popen([sys.executable, "-c", code, str(runtime / "quality-gate.lock")],
                                  stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True)
        self.addCleanup(lambda: (holder.kill(), holder.wait(), holder.stdout.close()))
        self.assertEqual(holder.stdout.readline().strip(), "held")

    def sequence(self, fx, steps=4):
        out = [fx.claude()]
        out += [fx.claude(continued=True) for _ in range(steps - 1)]
        return out

    def test_c_v4_gate_lock_with_v5_runner(self):
        fx = self.fixture({LOCK: baseline(LOCK)}, "c lock-v4+runner-v5")
        steps = self.sequence(fx)
        for step in steps:
            self.assertNeverPasses(step)
        # v4's execve-based lock still lets the v5 runner run (its --check sees the inherited descriptor). The
        # failing gate blocks once; the unchanged continued Stops are released UNVERIFIED by the v5 rule.
        self.assertEqual([s["verdict"] for s in steps], ["block", "release", "release", "release"], steps)
        self.assertIn("nothing changed", steps[1]["stdout"])

    def test_c_busy_path_still_counts_with_v4_lock(self):
        fx = self.fixture({LOCK: baseline(LOCK)}, "c lock-v4 busy")
        self.hold_lock(fx)
        steps = self.sequence(fx)
        self.assertEqual([s["verdict"] for s in steps], ["block", "block", "block", "release"], steps)
        self.assertIn("busy", steps[0]["stdout"].lower())
        self.assertIn("stayed busy", steps[-1]["stdout"])
        codex = [fx.codex(), fx.codex(continued=True), fx.codex(continued=True), fx.codex(continued=True)]
        self.assertEqual([s["verdict"] for s in codex], ["block", "block", "block", "release"], codex)
        self.assertIn("stayed busy", codex[-1]["stdout"])

    def test_c_codex_with_v4_lock_runs_gate(self):
        fx = self.fixture({LOCK: baseline(LOCK)}, "c lock-v4")
        steps = [fx.codex(), fx.codex(continued=True)]
        self.assertEqual(steps[0]["verdict"], "block", steps)
        self.assertNeverPasses(steps[1])

    def test_d_v5_lock_with_v4_runner(self):
        fx = self.fixture({RUNNER: baseline(RUNNER)}, "d lock-v5+runner-v4")
        steps = self.sequence(fx)
        for step in steps:
            self.assertNeverPasses(step)
        self.assertEqual(steps[0]["verdict"], "block", steps)
        self.assertEqual(steps[-1]["verdict"], "release", steps)
        self.assertEqual(steps[-1]["markers"].get(".gate-failed"), "4")  # v4 runner counts to the cap

    def test_d_busy_with_v4_runner(self):
        fx = self.fixture({RUNNER: baseline(RUNNER)}, "d runner-v4 busy")
        self.hold_lock(fx)
        steps = self.sequence(fx)
        for step in steps:
            self.assertNeverPasses(step)
        self.assertEqual(steps[0]["verdict"], "block", steps)
        self.assertEqual(steps[-1]["verdict"], "release", steps)
        codex = [fx.codex(), fx.codex(continued=True), fx.codex(continued=True), fx.codex(continued=True)]
        self.assertEqual([s["verdict"] for s in codex], ["block", "block", "block", "release"], codex)

    def test_d_codex_with_v4_runner(self):
        fx = self.fixture({RUNNER: baseline(RUNNER)}, "d runner-v4 codex")
        steps = [fx.codex(), fx.codex(continued=True)]
        self.assertEqual(steps[0]["verdict"], "block", steps)
        self.assertNeverPasses(steps[1])

    def test_e_v5_wrapper_with_v4_runner_and_back(self):
        fx = self.fixture({RUNNER: baseline(RUNNER)}, "e wrapper-v5+runner-v4")
        for step in self.sequence(fx):
            self.assertNeverPasses(step)
        fy = self.fixture({WRAPPER: baseline(WRAPPER)}, "e wrapper-v4+runner-v5")
        steps = self.sequence(fy)
        for step in steps:
            self.assertNeverPasses(step)
        self.assertEqual(steps[0]["verdict"], "block", steps)
        self.assertEqual(steps[-1]["verdict"], "release", steps)

    def test_e_v4_wrapper_busy_with_v5_runner(self):
        fy = self.fixture({WRAPPER: baseline(WRAPPER)}, "e wrapper-v4 busy")
        self.hold_lock(fy)
        steps = self.sequence(fy)
        for step in steps:
            self.assertNeverPasses(step)
        # known: the v4.17.0 wrapper has no busy counter, so a held lock blocks every Stop forever (a loop,
        # never a pass). v5's busy_stop is what bounds it.
        self.assertEqual([s["verdict"] for s in steps], ["block"] * 4, steps)


if __name__ == "__main__":
    unittest.main()
