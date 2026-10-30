"""High-risk floor and stale-review behavior for target gate entries."""
import json
from pathlib import Path
import shlex
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from target_support import TargetFixture  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import install  # noqa: E402


class TargetGateTests(TargetFixture):
    def test_target_high_risk_floor_applies_to_all_gate_entries_and_stale_reviews(self):
        context = self.install()
        marker = self.root / ".agent-runtime/target-check-ran"
        self.gate_file(context, "test -f app.txt && touch " + shlex.quote(str(marker)))
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt` and `secret/`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Registered target policy")
        self.assertEqual(self.gate_entry("shared", "--cache-tree").returncode, 0)
        self.bind("target-low", "Contract: risk=LOW quality=STANDARD acceptance=target fixture")
        target = Path(context["project_root"])
        (target / "app.txt").write_text("unreviewed target edit")
        for entry in ("shared", "standalone", "claude", "codex"):
            with self.subTest(entry=entry):
                marker.unlink(missing_ok=True)
                result = self.gate_entry(entry, session="target-low")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("targets/application/app.txt", result.stderr)
                self.assertTrue(marker.is_file(), "approved deterministic checks must precede review enforcement")
        self.reviewed()
        for entry in ("shared", "standalone", "claude", "codex"):
            result = self.gate_entry(entry, session="target-low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (target / "secret").mkdir()
        (target / "secret/new.txt").write_text("untracked risk invalidates review")
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, *(["--cache-tree"] if entry == "shared" else []))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("targets/application/secret/new.txt", result.stderr)

    def test_target_session_commit_and_pointer_update_keep_high_risk_floor(self):
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Registered target policy")
        self.evidence("seed-session", "--session", "target-session")
        target = Path(context["project_root"])
        (target / "app.txt").write_text("committed risk")
        self.git(target, "add", ".")
        self.git(target, "commit", "-qm", "Target edit")
        self.git(self.root, "add", "targets/application")
        self.git(self.root, "commit", "-qm", "Advance target pointer")
        self.evidence("seed-session", "--session", "target-session")  # Resume preserves initial pin.
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, "--session", "target-session")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("targets/application/app.txt", result.stderr)
        self.reviewed()
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, "--session", "target-session")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_target_added_after_session_start_reviews_all_new_high_risk_content(self):
        self.evidence("seed-session", "--session", "new-target")
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "New target is part of this session")
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, session="new-target")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("targets/application/app.txt", result.stderr)
        self.reviewed()
        self.assertEqual(self.gate_entry("standalone", session="new-target").returncode, 0)

    def test_inactive_target_risk_survives_clear_switch_and_session_commits(self):
        first = self.install()
        self.gate_file(first, "true")
        project = Path(first["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "First target policy")
        second_remote = self.make_remote("second")
        second = self.install(second_remote)
        self.gate_file(second, "true")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Second target policy")
        self.install()
        self.evidence("seed-session", "--session", "inactive-risk")
        self.bind("inactive-risk", "Contract: risk=LOW quality=STANDARD acceptance=inactive target")
        target = Path(first["project_root"])
        (target / "app.txt").write_text("unreviewed inactive target")
        for selection in ("clear", "switch"):
            self.cli("clear") if selection == "clear" else self.install(second_remote)
            for entry in ("shared", "claude", "codex"):
                with self.subTest(selection=selection, entry=entry):
                    result = self.gate_entry(entry, session="inactive-risk")
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("targets/application/app.txt", result.stderr)
            # Once another application is selected, its standalone gate enforces the root receipt too.
            if selection == "switch":
                result = self.gate_entry("standalone", session="inactive-risk")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("targets/application/app.txt", result.stderr)
        self.git(target, "add", ".")
        self.git(target, "commit", "-qm", "Commit inactive target risk")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Commit inactive target pin")
        self.cli("clear")
        result = self.gate_entry("shared", session="inactive-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("targets/application/app.txt", result.stderr)
        self.reviewed()
        for entry in ("shared", "claude", "codex"):
            result = self.gate_entry(entry, session="inactive-risk")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (target / "app.txt").write_text("later inactive target edit")
        result = self.gate_entry("shared", session="inactive-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("targets/application/app.txt", result.stderr)

    def test_target_gate_failure_logs_real_reason_and_check_count_in_activity(self):
        context = self.install()
        self.gate_file(context, "true\necho BOOM; exit 1")
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        activity_file = self.root / ".agent-runtime/activity.jsonl"
        events = [json.loads(line) for line in activity_file.read_text().splitlines() if line.strip()]
        gate_events = [event for event in events if event.get("event") == "gate"]
        self.assertTrue(gate_events)
        last = gate_events[-1]
        self.assertEqual(last["result"], "refused")
        self.assertEqual(last["checks"], 3)
        self.assertTrue(last.get("reason", "").startswith("Target Quality Gate failed (1):"), last)

    def test_target_gate_cache_tree_reuses_unchanged_target_across_record_updates(self):
        context = self.install()
        counter = self.root / ".agent-runtime/target-runs"
        self.gate_file(context, f"printf 'run\\n' >> {shlex.quote(str(counter))}")
        first = self.gate_entry("shared", "--cache-tree")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(counter.read_text().splitlines(), ["run"])

        (Path(context["record_root"]) / "notes.md").write_text("record update outside target checkout\n")
        second = self.gate_entry("shared", "--cache-tree")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(counter.read_text().splitlines(), ["run"])
        self.assertIn("Target Quality Gate: checks reused for the unchanged target state", second.stderr)

        (Path(context["project_root"]) / "app.txt").write_text("modified application file\n")
        third = self.gate_entry("shared", "--cache-tree")
        self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
        self.assertEqual(counter.read_text().splitlines(), ["run", "run"])


if __name__ == "__main__":
    unittest.main()
