"""Target control drift, trust and boundaries for deinitialized or unborn targets."""
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from target_support import TargetFixture  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import install  # noqa: E402


class TargetControlTests(TargetFixture):
    def test_unborn_parent_target_uses_index_and_session_new_content_boundaries(self):
        self.git(self.root, "checkout", "--orphan", "unborn")
        self.evidence("seed-session", "--session", "unborn-target")
        self.bind("unborn-target", "Contract: risk=LOW quality=STANDARD acceptance=new target")
        context = self.install()
        self.gate_file(context, "true")
        for entry in ("shared", "standalone", "claude", "codex"):
            result = self.gate_entry(entry)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        # Direct validation uses the staged pin in an unborn parent.
        self.assertEqual(self.gate_entry("shared").returncode, 0)
        # A session begun before any parent commit owns all newly registered app content.
        for committed in (False, True):
            if committed:
                self.git(self.root, "add", ".")
                self.git(self.root, "commit", "-qm", "First parent commit with new target")
            for entry in ("shared", "standalone", "claude", "codex"):
                with self.subTest(committed=committed, entry=entry):
                    result = self.gate_entry(entry, session="unborn-target")
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("targets/application/app.txt", result.stderr)

    def test_unchanged_deinitialized_retained_target_does_not_block_root_gate(self):
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Retained target policy")
        self.cli("clear")
        self.git(self.root, "submodule", "deinit", "-f", "--", "targets/application")
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_deinitialized_target_and_explicit_missing_baseline_fail_closed(self):
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Target policy baseline")
        self.evidence("seed-session", "--session", "deinitialized-risk")
        target = Path(context["project_root"])
        (target / "app.txt").write_text("changed target pin")
        self.git(target, "add", ".")
        self.git(target, "commit", "-qm", "New target content")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Advance target pin")
        self.cli("clear")
        self.git(self.root, "submodule", "deinit", "-f", "--", "targets/application")
        result = self.gate_entry("shared", session="deinitialized-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Changed target submodule is not initialized", result.stderr)
        # Only an optional HEAD can fall back to the index; a recorded unavailable tree cannot.
        (self.root / ".agent-runtime/gate-baseline-head").write_text("1" * 40)
        result = self.command(sys.executable, self.lean, "--root", self.root, "evidence", "high-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ls-tree", result.stderr)

    def test_target_control_drift_never_executes_before_guard_in_any_entry(self):
        context = self.install()
        self.gate_file(context, "true")
        self.assertEqual(self.gate_entry("shared").returncode, 0)
        self.gate_file(context, "false")
        self.evidence("accept-controls", "--reason", "fixture author approved failing target command")
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Target Quality Gate failed", result.stderr)
        baseline = (self.root / ".agent-runtime/gate-controls.json").read_bytes()
        self.gate_file(context, ":; touch escaped-control")
        for entry in ("standalone", "shared", "claude", "codex"):
            with self.subTest(entry=entry):
                result = self.gate_entry(entry)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("Protected gate controls changed", result.stderr)
                self.assertFalse((Path(context["project_root"]) / "escaped-control").exists())
                self.assertEqual((self.root / ".agent-runtime/gate-controls.json").read_bytes(), baseline)

    def test_switching_target_does_not_approve_inactive_gate_drift(self):
        first = self.install()
        self.gate_file(first, "true")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "First registered target")
        second = self.install(self.make_remote("second"))
        self.gate_file(second, "true")
        self.assertEqual(self.gate_entry("shared").returncode, 0)
        self.gate_file(first, "touch inactive-control")
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Protected gate controls changed", result.stderr)
        self.install()
        self.assertEqual(self.gate_entry("standalone").returncode, 2)
        self.assertFalse((Path(first["project_root"]) / "inactive-control").exists())

    def test_target_control_review_uses_root_session_trust_for_all_entries(self):
        context = self.install()
        self.gate_file(context, "true")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Baseline target checks")
        self.assertEqual(self.gate_entry("standalone").returncode, 0)
        contract = "Contract: risk=HIGH quality=HIGH acceptance=review target controls"
        self.bind("target-controls", contract)
        for entry in ("standalone", "shared", "claude", "codex"):
            with self.subTest(entry=entry):
                self.gate_file(context, "true # reviewed " + entry)
                rejected = self.gate_entry(entry, session="target-controls")
                self.assertEqual(rejected.returncode, 2, rejected.stdout + rejected.stderr)
                self.assertIn("Protected gate controls changed", rejected.stderr)
                self.reviewed(contract)
                # A receipt alone cannot accept drift without the session's declared contract.
                unbound = self.gate_entry("standalone")
                self.assertEqual(unbound.returncode, 2, unbound.stderr)
                accepted = self.gate_entry(entry, session="target-controls")
                self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
                history = json.loads((self.root / ".agent-runtime/gate-controls.json").read_text())["history"]
                self.assertIn("independent HIGH-depth", history[-1]["reason"])
                self.git(self.root, "add", ".")
                self.git(self.root, "commit", "-qm", "Accept reviewed target checks " + entry)

    def test_target_controls_match_trusted_root_ref_and_reject_retained_symlinks(self):
        context = self.install()
        self.gate_file(context, "true")
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n<!-- trusted-control-refs: refs/remotes/origin/main -->\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Baseline targets and trusted ref")
        self.git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.assertEqual(self.gate_entry("standalone").returncode, 0)
        self.gate_file(context, "true # trusted target gate")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Upstream reviewed target gate")
        self.git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")
        result = self.gate_entry("standalone")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("match refs/remotes/origin/main", result.stderr)
        # Retained records are checked even with no selected target.
        self.cli("clear")
        target_project = Path(context["project_file"])
        external = self.base / "external PROJECT.md"
        external.write_bytes(target_project.read_bytes())
        target_project.unlink()
        target_project.symlink_to(external)
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("symlink boundary", result.stderr)


if __name__ == "__main__":
    unittest.main()
