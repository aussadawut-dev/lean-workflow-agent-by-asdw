"""Pure-rule tests for lean_core, plus a parity check against the real Codex refusal code."""
import importlib.util
import io
import json
import os
import contextlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load("lean_core", ".lean/scripts/lean_core.py")


class ValidSessionKeyTests(unittest.TestCase):
    def test_properties(self):
        good = ("0123456789abcdef", "a" * 16, core.session_key("session-1"), core.session_key("päth\t"))
        for key in good:
            self.assertIs(core.valid_session_key(key), True, key)
        bad = ("", "../../../escape", "A" * 16, "a" * 15, "a" * 17, "0123456789abcdeg", "0123456789abcde\n",
               "0123456789abcde/", " " + "a" * 15, "\u0661" * 16, 1234567890123456, None, b"a" * 16, ["a"] * 16)
        for key in bad:
            self.assertIs(core.valid_session_key(key), False, key)

    def test_every_session_key_is_valid(self):
        for session in ("s", "x" * 500, "\ud800", "with/slash", "../.."):
            self.assertTrue(core.valid_session_key(core.session_key(session)), session)


class GateRefusalTests(unittest.TestCase):
    def test_fresh_stop_restarts_count(self):
        self.assertEqual(core.gate_refusal("3", False, False, False), (core.BLOCK, "1"))

    def test_continued_counts_up_and_caps(self):
        self.assertEqual(core.gate_refusal("1", True, False, False), (core.BLOCK, "2"))
        self.assertEqual(core.gate_refusal("2", True, False, False), (core.BLOCK, "3"))
        self.assertEqual(core.gate_refusal("3", True, False, False), (core.RELEASE_CAPPED, "4"))

    def test_contract_refusal_marker_and_count(self):
        self.assertEqual(core.gate_refusal("c1", True, True, False), (core.BLOCK, "c2"))

    def test_unchanged_repeat_releases_before_cap(self):
        self.assertEqual(core.gate_refusal("1", True, False, True), (core.RELEASE_UNCHANGED, "2"))

    def test_unchanged_release_wins_over_cap(self):
        # Both v4 implementations check "nothing changed" before the cap; the count is still recorded.
        self.assertEqual(core.gate_refusal("5", True, False, True), (core.RELEASE_UNCHANGED, "6"))
        self.assertEqual(core.gate_refusal("5", True, False, False), (core.RELEASE_CAPPED, "6"))

    def test_contract_refusal_never_releases_as_unchanged(self):
        self.assertEqual(core.gate_refusal("", False, True, True), (core.BLOCK, "c1"))

    def test_garbage_marker_counts_as_zero(self):
        self.assertEqual(core.gate_refusal("xyz", True, False, False), (core.BLOCK, "1"))

    def test_non_ascii_digit_marker_counts_as_zero_without_raising(self):
        for raw in ("\u00b2", "c\u00b3", "\u0663", "1\u00b2"):
            self.assertEqual(core.gate_refusal(raw, True, False, False), (core.BLOCK, "1"), raw)

    def test_shell_embedded_call_survives_non_ascii_digit(self):
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import lean_core\n'
                'print(*lean_core.gate_refusal(sys.argv[2], True, False, False))')
        out = subprocess.run(["python3", "-c", code, str(ROOT / ".lean/scripts"), "\u00b2"],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual((out.returncode, out.stdout.split()), (0, [core.BLOCK, "1"]), out.stderr)


class CodexRefusalParityTests(unittest.TestCase):
    """The Codex adapter's refuse() must agree with the core for counting, cap and marker."""

    def run_refuse(self, codex, previous, continued, is_contract):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agent-runtime").mkdir()
            if previous:
                (root / ".agent-runtime/codex-gate-failed").write_text(previous)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                codex.refuse(root, {"stop_hook_active": continued}, "detail", is_contract=is_contract)
            marker = (root / ".agent-runtime/codex-gate-failed").read_text()
            released = "released UNVERIFIED" in out.getvalue() or json.loads(out.getvalue()).get("decision") != "block"
            return marker, released

    def test_counting_and_cap_match(self):
        codex = load("codex_quality_gate", ".codex/hooks/quality_gate.py")
        for previous, continued, is_contract in [("", False, False), ("1", True, False), ("2", True, False),
                                                 ("3", True, False), ("3", False, False), ("c1", True, True),
                                                 ("c3", True, True)]:
            action, marker = core.gate_refusal(previous, continued, is_contract, False)
            got_marker, released = self.run_refuse(codex, previous, continued, is_contract)
            self.assertEqual(got_marker, marker, (previous, continued, is_contract))
            self.assertEqual(released, action != core.BLOCK, (previous, continued, is_contract))


class ShellRefusalParityTests(unittest.TestCase):
    """The Claude shell gate's refusal path must agree with the core, step by step.

    The core is the oracle for (action, marker); the shell is run for real against a failing gate in a
    throwaway repository. `change` alters a Git-visible file before a step so the fingerprint differs.
    """

    SCRIPTS = (".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py", ".lean/scripts/gate_lock.py",
               ".lean/scripts/gate_mode.py", ".lean/scripts/lean_core.py", ".lean/scripts/contract_guard.py",
               ".claude/hooks/quality-gate.sh",
               ".claude/hooks/session-start.sh", ".gitignore")

    def make_repo(self):
        tmp = tempfile.TemporaryDirectory(prefix="lean core shell ")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in self.SCRIPTS:
            if (ROOT / name).exists():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, root / name)
        (root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        (root / ".claude/settings.json").write_text("{}")
        git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "init"], check=True)
        accepted = subprocess.run(["python3", str(root / ".lean/scripts/gate_evidence.py"), "--root", str(root),
                                   "accept-controls", "--reason", "Fixture selects a failing gate"],
                                  capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        return root

    def shell_step(self, root, continued, session, contract=False, env=None):
        payload = {"stop_hook_active": continued}
        if session:
            payload["session_id"] = session
        if contract:
            # No declared contract and an unreadable transcript: the gate refuses about the contract.
            payload["transcript_path"] = str(root / "missing-transcript.jsonl")
        result = subprocess.run(["bash", str(root / ".lean/scripts/quality-gate.sh"), "--root", str(root),
                                 "--claude-hook"], input=json.dumps(payload), text=True, capture_output=True, env=env)
        marker = root / (f".agent-runtime/gate-failed.{core.session_key(session)}" if session else ".claude/.gate-failed")
        if not marker.exists():  # a core that cannot run leaves the key empty: the legacy name is used
            marker = root / ".claude/.gate-failed"
        text = marker.read_text() if marker.exists() else None
        if result.returncode == 2:
            return core.BLOCK, text
        message = json.loads(result.stdout)["systemMessage"]
        if "nothing changed" in message:
            return core.RELEASE_UNCHANGED, text
        self.assertIn("still refused after", message)
        return core.RELEASE_CAPPED, text

    def run_sequence(self, steps, session="s", contract=False):
        """steps: (continued, change). Compare every step with the core."""
        root = self.make_repo()
        previous, recorded, current = "", None, 0
        for index, (continued, change) in enumerate(steps):
            if change:
                current += 1
                (root / "work.txt").write_text(f"change {current}\n")
            same = bool(session) and recorded == current
            action, marker = core.gate_refusal(previous, continued, contract, same)
            got_action, got_marker = self.shell_step(root, continued, session, contract)
            self.assertEqual((got_action, got_marker), (action, marker), (index, steps))
            previous = marker
            if session:
                recorded = current if action != core.RELEASE_UNCHANGED else recorded

    def test_changing_state_counts_and_caps(self):
        self.run_sequence([(False, True), (True, True), (True, True), (True, True), (False, True)])

    def test_unchanged_repeat_releases_then_new_work_blocks(self):
        self.run_sequence([(False, True), (True, False), (False, False), (True, True)])

    def test_unchanged_release_wins_over_the_cap(self):
        # Count 4 would be a capped release, but nothing changed since the last refusal: the shell and the
        # core both report the "nothing changed" release first.
        self.run_sequence([(False, True), (True, True), (True, True), (True, False)])

    def test_contract_refusals_count_with_a_c_marker_and_cap(self):
        # Contract refusals never take the "nothing changed" release, even with an identical state.
        self.run_sequence([(False, True), (True, False), (True, False), (True, False), (False, False)],
                          contract=True)

    def test_without_a_session_only_the_cap_applies(self):
        self.run_sequence([(False, True), (True, False), (True, False), (True, False)], session="")

    def test_v4_sequence_is_pinned_independently_of_the_core(self):
        # The shell now runs the core, so core-vs-shell parity cannot catch a wrong rule. These are the v4.17.0
        # outcomes written out: block at 1, 2 and 3, capped release at 4; an unchanged repeat releases first.
        root = self.make_repo()
        seen = []
        for continued in (False, True, True, True):
            (root / "work.txt").write_text(f"change {len(seen)}\n")
            seen.append(self.shell_step(root, continued, "s"))
        self.assertEqual(seen, [(core.BLOCK, "1"), (core.BLOCK, "2"), (core.BLOCK, "3"), (core.RELEASE_CAPPED, "4")])
        self.assertEqual(self.shell_step(root, True, "s"), (core.RELEASE_UNCHANGED, "5"))

    def test_unavailable_core_blocks_a_fresh_stop_and_releases_a_continued_one(self):
        # A `python3` that fails only for `-c` stands in for a core that cannot run, without changing
        # any protected control: the decision falls back, and a regression here would loop or pass silently.
        root = self.make_repo()
        shim = root.parent / (root.name + " bin")
        shim.mkdir()
        real = shutil.which("python3")
        (shim / "python3").write_text(f'#!/bin/sh\n[ "$1" = "-c" ] && exit 1\nexec "{real}" "$@"\n')
        (shim / "python3").chmod(0o755)
        self.addCleanup(shutil.rmtree, shim, True)
        env = {**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}
        self.assertEqual(self.shell_step(root, False, "s", env=env), (core.BLOCK, "1"))
        self.assertEqual(self.shell_step(root, True, "s", env=env), (core.RELEASE_CAPPED, "4"))


class CodexRefusalSequenceParityTests(unittest.TestCase):
    """Codex `refuse()` against the core over whole sequences, including the "nothing changed" release.

    Runs in a real Git repository so the adapter can fingerprint the shipping state; `session` is set.
    """

    def codex_step(self, codex, root, continued, change_to, is_contract):
        if change_to is not None:
            (root / "work.txt").write_text(f"change {change_to}\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            codex.refuse(root, {"stop_hook_active": continued}, "detail", session="s", contract="C",
                         is_contract=is_contract)
        marker = (root / f".agent-runtime/codex-gate-failed.{core.session_key('s')}").read_text()
        message = json.loads(out.getvalue())
        if message.get("decision") == "block":
            return core.BLOCK, marker
        if "nothing changed" in message["systemMessage"]:
            return core.RELEASE_UNCHANGED, marker
        self.assertIn("still refused after", message["systemMessage"])
        return core.RELEASE_CAPPED, marker

    def run_sequence(self, steps, is_contract=False):
        codex = load("codex_quality_gate_seq", ".codex/hooks/quality_gate.py")
        with tempfile.TemporaryDirectory(prefix="lean core codex ") as tmp:
            root = Path(tmp)
            git = ["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run([*git, "init", "-q"], check=True)
            (root / "seed.txt").write_text("seed\n")
            # Runtime markers must stay out of the fingerprinted state, as in a real project.
            shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run([*git, "commit", "-qm", "init"], check=True)
            previous, recorded, current = "", None, 0
            for index, (continued, change) in enumerate(steps):
                if change:
                    current += 1
                same = recorded == current and not is_contract
                action, marker = core.gate_refusal(previous, continued, is_contract, same)
                got = self.codex_step(codex, root, continued, current if change else None, is_contract)
                self.assertEqual(got, (action, marker), (index, steps))
                previous = marker
                if not is_contract and action != core.RELEASE_UNCHANGED:
                    recorded = current

    def test_changing_state_counts_and_caps(self):
        self.run_sequence([(False, True), (True, True), (True, True), (True, True), (False, True)])

    def test_unchanged_repeat_releases_then_new_work_blocks(self):
        self.run_sequence([(False, True), (True, False), (False, False), (True, True)])

    def test_unchanged_release_wins_over_the_cap(self):
        self.run_sequence([(False, True), (True, True), (True, True), (True, False)])

    def test_unreadable_refusal_file_keeps_the_counted_decision(self):
        # HEAD computed and persisted the count before reading the refusal file, so an unreadable
        # fingerprint file never loses the count or evades the cap.
        codex = load("codex_quality_gate_unreadable", ".codex/hooks/quality_gate.py")
        with tempfile.TemporaryDirectory(prefix="lean core codex ") as tmp:
            root = Path(tmp)
            git = ["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run([*git, "init", "-q"], check=True)
            (root / "seed.txt").write_text("seed\n")
            shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run([*git, "commit", "-qm", "init"], check=True)
            runtime = root / ".agent-runtime"
            runtime.mkdir()
            suffix = f".{core.session_key('s')}"
            (runtime / f"codex-gate-failed{suffix}").write_text("1")
            (runtime / f"codex-gate-refusal{suffix}").write_bytes(b"\xff\xfe not utf8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                codex.refuse(root, {"stop_hook_active": True}, "detail", session="s", contract="C")
            self.assertEqual(json.loads(out.getvalue()).get("decision"), "block")
            self.assertEqual((runtime / f"codex-gate-failed{suffix}").read_text(), "2")

    def test_contract_refusals_count_cap_and_never_release_as_unchanged(self):
        self.run_sequence([(False, True), (True, False), (True, False), (True, False), (False, False)],
                          is_contract=True)


if __name__ == "__main__":
    unittest.main()
