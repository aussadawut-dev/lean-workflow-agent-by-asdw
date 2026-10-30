"""Target tracker closure receipts retain requirements and shipping integrity."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, git, install, lean  # noqa: E402


CONTRACT = "Contract: risk=HIGH quality=HIGH acceptance=tracker fixture passes"
LOW = "Contract: risk=LOW quality=STANDARD acceptance=tracker fixture passes"
NAME = ".lean/targets/app/docs/tracking/TCK001-fix.md"
TRACKER = """# TCK001 — Fix the application

Status: REVIEWING
Owner: developer
Priority: urgent

## Goal

Keep requirements covered.

## Acceptance criteria

- [ ] AC-01: Preserve acceptance text.

## Tasks

1. [ ] TASK-01: Preserve task text.

## Decisions

- Keep the API stable.

## Evidence

- Tests passed.

## Evidence guidance

Record verified commands.

## Next step

Record the review.
"""
CLOSED = TRACKER.replace("Status: REVIEWING", "Status: DONE").replace("[ ]", "[x]").replace(
    "- Tests passed.", "- Tests and independent review passed.\n- Gate PASS.").replace(
    "Record the review.", "No remaining work.")


class TargetTrackerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean tracker receipt ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)
        (self.root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\ntrue\n<!-- gate:end -->\n")
        self.path = self.write(NAME, TRACKER)
        git(self.root, "init", "-q")
        commit(self.root, "base")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def evidence(self, *args):
        return lean(self.root, "evidence", *args)

    def record(self, contract=CONTRACT):
        snapshot = self.evidence("state")
        self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
        result = self.evidence("record-review", "--state", snapshot.stdout.strip(), "--contract", contract,
                               "--reviewer", "independent-fixture", "--evidence", "fixture review", "--verdict", "PASS")
        self.assertEqual(result.returncode, 0, result.stderr)

    def covered(self, expected=True, contract=CONTRACT):
        result = self.evidence("check-review", "--contract", contract)
        self.assertEqual(result.returncode == 0, expected, result.stderr)

    def test_closure_survives_worktree_staging_and_committing(self):
        self.record()
        self.path.write_text(CLOSED)
        self.covered()
        git(self.root, "add", NAME)
        self.covered()
        commit(self.root, "close tracker")
        self.covered()
        self.assertEqual(self.evidence("check-shipped").returncode, 0)

    def test_each_closure_field_is_mutable(self):
        self.record()
        for text in (TRACKER.replace("REVIEWING", "VALIDATING"), TRACKER.replace("[ ]", "[X]"),
                     TRACKER.replace("- Tests passed.", "- New verified evidence.\n\n### Results\n\nPASS"),
                     TRACKER.replace("Record the review.", "Close the tracker.")):
            with self.subTest(text=text):
                self.path.write_text(text)
                self.covered()

    def test_existing_tracker_layout_variants_preserve_closure(self):
        expanded = TRACKER.replace("## Acceptance criteria", "## Scope\n\nApplication scope.\n\n"
                                   "## Constraints\n\nKeep compatibility.\n\n## Acceptance criteria").replace(
            "## Decisions", "## Decisions and assumptions").replace(
            "## Evidence\n", "## Dependencies and risks\n\nNo new dependencies.\n\n## Evidence\n")
        finding = """# TCK001 — Fix the application

Status: REVIEWING
Owner: developer

## Finding

Keep the observed requirement covered.

## Acceptance criteria

- [ ] AC-01: Preserve acceptance text.

## Dependencies

Keep the existing dependency.

## Evidence

- Tests passed.

## Tasks

- [ ] TASK-01: Preserve task text.

## Next step

Record the review.

## Closure — 2026-10-30

Retain existing closure metadata.
"""
        for text in (expanded, finding):
            with self.subTest(layout=text):
                self.path.write_text(text)
                self.record()
                self.path.write_text(text.replace("REVIEWING", "DONE").replace("[ ]", "[x]").replace(
                    "- Tests passed.", "- Tests and review passed.").replace("Record the review.", "Finished."))
                self.covered()
                git(self.root, "add", NAME)
                self.covered()
                commit(self.root, "close existing layout")
                self.covered()
                self.path.write_text(self.path.read_text().replace("Preserve acceptance text.", "Changed scope."))
                self.covered(False)

    def test_fenced_headings_are_content_and_fenced_requirements_stay_covered(self):
        text = TRACKER.replace("Keep requirements covered.", "Keep requirements covered.\n\n```md\n"
                               "## Evidence\nStatus: DONE\nOwner: example\n```\n").replace(
            "- Tests passed.", "- Tests passed.\n\n~~~sh\n## Goal\nStatus: example\n~~~")
        self.path.write_text(text)
        self.record()
        self.path.write_text(text.replace("Status: REVIEWING", "Status: DONE").replace("- Tests passed.",
                                                                                    "- New verified results."))
        self.covered()
        self.path.write_text(text.replace("## Evidence\nStatus: DONE", "## Evidence\nStatus: FAILED"))
        self.covered(False)

    def test_fenced_checklist_markers_are_requirement_bytes(self):
        text = TRACKER.replace("## Decisions", "```md\n- [ ] Example checkbox\n```\n\n## Decisions")
        self.path.write_text(text)
        self.record()
        self.path.write_text(text.replace("[ ] Example checkbox", "[x] Example checkbox"))
        self.covered(False)

    def test_requirement_and_metadata_edits_stale_review(self):
        self.record()
        for old, new in (("Keep requirements covered.", "Drop requirements."),
                         ("Preserve acceptance text.", "Drop acceptance."),
                         ("Preserve task text.", "Drop task."),
                         ("Keep the API stable.", "Change the API."),
                         ("Owner: developer", "Owner: someone else"),
                         ("Priority: urgent", "Priority: low"),
                         ("Record verified commands.", "Skip verification."),
                         ("Fix the application", "Change scope")):
            with self.subTest(field=old):
                self.path.write_text(TRACKER.replace(old, new))
                self.covered(False)
        self.path.write_text(TRACKER)
        self.covered()

    def test_decision_checkbox_remains_meaningful(self):
        text = TRACKER.replace("- Keep the API stable.", "- [ ] Keep the API stable.")
        self.path.write_text(text)
        self.record()
        self.path.write_text(text.replace("- [ ] Keep", "- [x] Keep"))
        self.covered(False)

    def test_unknown_sections_remain_meaningful(self):
        text = TRACKER + "\n## User notes\n\nPreserve this metadata.\n"
        self.path.write_text(text)
        self.record()
        self.path.write_text(text.replace("Preserve this metadata.", "Change metadata."))
        self.covered(False)

    def test_nonstandard_trackers_fall_back_to_raw_bytes(self):
        for text in (TRACKER.replace("REVIEWING", "UNKNOWN"),
                     TRACKER.replace("Owner: developer\n", ""),
                     TRACKER.replace("## Tasks", "## Work"),
                     TRACKER.replace("# TCK001", "# TCK002"),
                     TRACKER.replace("## Evidence\n", "## Evidence\n\n## Evidence\n"),
                     TRACKER.replace("## Evidence\n", "## Evidence\n\n## evidence\n"),
                     TRACKER.replace("## Goal", "  ## Goal"),
                     TRACKER.replace("## Evidence\n", "## Evidence\n\n```md\n## Decisions\n"),
                     TRACKER.replace("## Evidence\n", "## Evidence\n\n~~~md\n## Decisions\n"),
                     TRACKER.replace("Status: REVIEWING", "Status: REVIEWING\nStatus: PLANNED"),
                     "Status: REVIEWING\n- [ ] Task\n"):
            with self.subTest(text=text):
                self.path.write_text(text)
                self.record()
                self.path.write_text(text + "\n")
                self.covered(False)

    def test_malformed_utf8_is_raw_covered(self):
        self.path.write_bytes(TRACKER.encode() + b"\xff")
        self.record()
        self.path.write_bytes(CLOSED.encode() + b"\xff")
        self.covered(False)

    def test_name_and_directory_boundaries_are_raw(self):
        for name in (".lean/targets/app/docs/tracking/TCK01.md",
                     ".lean/targets/app/docs/tracking/TCK001.bad.md",
                     ".lean/targets/app/docs/tracking/notes/TCK001.md",
                     ".lean/targets/app/docs/tracking/README.md",
                     ".lean/targets/app/docs/other/TCK001.md"):
            with self.subTest(name=name):
                path = self.write(name, TRACKER)
                self.record()
                path.write_text(CLOSED)
                self.covered(False)
                path.unlink()

    def test_symlink_and_mode_changes_stale_review(self):
        self.record()
        os.chmod(self.path, 0o755)
        self.covered(False)
        os.chmod(self.path, 0o644)
        self.path.unlink()
        self.write("closure.md", CLOSED)
        self.path.symlink_to("../../../../../closure.md")
        self.covered(False)

    def test_symlink_tracker_is_raw_even_when_destination_is_valid(self):
        self.path.unlink()
        first = self.write("first.md", TRACKER)
        second = self.write("second.md", CLOSED)
        self.path.symlink_to(first)
        self.record()
        self.path.unlink()
        self.path.symlink_to(second)
        self.covered(False)

    def test_symlink_directory_cannot_enable_projection(self):
        tracking = self.path.parent
        destination = self.root / "moved-records"
        tracking.rename(destination)
        tracking.symlink_to(destination, target_is_directory=True)
        self.record()
        (destination / self.path.name).write_text(CLOSED)
        self.covered(False)

    def test_gate_state_still_hashes_closure_bytes(self):
        self.record()
        before = self.evidence("gate-state").stdout
        self.path.write_text(CLOSED)
        self.covered()
        self.assertNotEqual(self.evidence("gate-state").stdout, before)

    def test_staged_closure_can_differ_from_reviewed_worktree(self):
        self.record()
        self.path.write_text(CLOSED)
        git(self.root, "add", NAME)
        self.path.write_text(TRACKER)
        self.covered()

    def test_staged_requirement_cannot_hide_behind_restored_worktree(self):
        self.record()
        self.path.write_text(TRACKER.replace("Preserve acceptance text.", "Unreviewed acceptance."))
        git(self.root, "add", NAME)
        self.path.write_text(TRACKER)
        self.covered(False)

    def test_committed_requirement_cannot_hide_behind_restored_worktree(self):
        self.record()
        self.path.write_text(TRACKER.replace("Keep requirements covered.", "Unreviewed goal."))
        commit(self.root, "unreviewed requirement")
        self.path.write_text(TRACKER)
        self.covered(False)

    def test_committed_closure_can_differ_from_reviewed_worktree(self):
        self.record()
        self.path.write_text(CLOSED)
        commit(self.root, "closure only")
        self.path.write_text(TRACKER)
        self.covered()

    def test_partial_semantic_commit_of_reviewed_trackers_is_rejected(self):
        other_name = ".lean/targets/app/docs/tracking/TCK002.md"
        other = self.write(other_name, TRACKER.replace("TCK001", "TCK002"))
        commit(self.root, "two trackers")
        self.path.write_text(TRACKER.replace("Keep requirements covered.", "Reviewed first goal."))
        other.write_text(other.read_text().replace("Keep requirements covered.", "Reviewed second goal."))
        self.record()
        git(self.root, "add", NAME)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=test", "-c",
                        "user.email=test@example.invalid", "commit", "-qm", "partial review"], check=True)
        self.covered(False)
        commit(self.root, "whole review")
        self.covered()

    def test_index_requirement_is_checked_even_after_head_moved(self):
        self.record()
        self.path.write_text(CLOSED)
        commit(self.root, "closure only")
        self.path.write_text(TRACKER.replace("Owner: developer", "Owner: unreviewed"))
        git(self.root, "add", NAME)
        self.path.write_text(TRACKER)
        self.covered(False)

    def test_staged_and_committed_mode_changes_cannot_hide(self):
        self.record()
        git(self.root, "config", "core.fileMode", "false")
        git(self.root, "update-index", "--chmod=+x", NAME)
        self.covered(False)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=test", "-c",
                        "user.email=test@example.invalid", "commit", "-qm", "mode"], check=True)
        self.covered(False)

    def test_staged_and_committed_symlink_cannot_hide(self):
        self.record()
        self.path.unlink()
        self.path.symlink_to("unreviewed-target")
        git(self.root, "add", NAME)
        self.path.unlink()
        self.path.write_text(TRACKER)
        self.covered(False)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=test", "-c",
                        "user.email=test@example.invalid", "commit", "-qm", "symlink"], check=True)
        self.covered(False)

    def test_new_tracker_and_removal_are_reviewed(self):
        self.record()
        new = self.write(".lean/targets/app/docs/tracking/TCK002.md", TRACKER.replace("TCK001", "TCK002"))
        self.covered(False)
        new.unlink()
        self.covered()
        self.path.unlink()
        self.covered(False)

    def test_reviewed_creation_and_deletion_survive_shipping(self):
        self.path.unlink()
        self.write(".lean/targets/app/docs/tracking/TCK002.md", TRACKER.replace("TCK001", "TCK002"))
        self.record()
        git(self.root, "add", "-A")
        self.covered()
        commit(self.root, "reviewed tracker replacement")
        self.covered()

    def test_staged_and_committed_deletion_cannot_hide_on_disk(self):
        self.record()
        git(self.root, "rm", "-q", "--cached", NAME)
        self.covered(False)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=test", "-c",
                        "user.email=test@example.invalid", "commit", "-qm", "drop tracker"], check=True)
        self.covered(False)

    def test_low_depth_receipt_keeps_its_existing_depth_boundary(self):
        self.record(LOW)
        self.path.write_text(CLOSED)
        self.covered(contract=LOW)
        self.assertNotEqual(self.evidence("check-shipped").returncode, 0)

    def test_receipt_metadata_requires_typed_nonempty_fields(self):
        self.record()
        path = self.root / ".agent-runtime/review.json"
        original = json.loads(path.read_text())
        for field, value in (("schema", True), ("schema", 1.0), ("reviewer", ["name"]),
                             ("reviewer", " "), ("evidence", {"claim": "PASS"}), ("evidence", "\t")):
            path.write_text(json.dumps(dict(original, **{field: value})))
            for command in (("check-review", "--contract", CONTRACT), ("check-shipped",)):
                with self.subTest(field=field, value=value, command=command):
                    result = self.evidence(*command)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_duplicate_receipt_keys_are_refused(self):
        self.record()
        path = self.root / ".agent-runtime/review.json"
        content = path.read_text().rstrip()
        path.write_text(content[:-1] + ', "schema": 1}\n')
        for command in (("check-review", "--contract", CONTRACT), ("check-shipped",)):
            with self.subTest(command=command):
                result = self.evidence(*command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("duplicate JSON key", result.stderr)

    def test_legacy_workspace_and_target_intake_exclusions_are_unchanged(self):
        self.record()
        self.write("docs/tracking/TCK001.md", "Status: DONE\n")
        self.write(".lean/targets/app/docs/tracking/INTAKE.md", "New intake record\n")
        self.covered()


if __name__ == "__main__":
    unittest.main()
