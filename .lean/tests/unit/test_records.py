"""Behavior checks for repository modes and full-mode queue ownership."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, passing_gate  # noqa: E402
from lean import records as workflow  # noqa: E402

SCRIPT = ROOT / ".lean/bin/lean"
TEMPLATES = ROOT / ".lean/templates"
MODE_ACTIONS = ("configure", "downgrade", "show", "check", "context")


def cli(*args):
    """The v5 spelling of a 4.x workflow.py call: mode actions moved under `lean mode`."""
    return ("mode", *args) if args and args[0] in MODE_ACTIONS else args


class WorkflowModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / ".lean/templates").mkdir(parents=True)
        for name in ("tracker.md", "queue-item.json"):
            (self.root / ".lean/templates" / name).write_text((TEMPLATES / name).read_text())
        (self.root / ".gitignore").write_text(".env\n")
        self.claim_counter = 0

    def run_cli(self, *args, success=True):
        if len(args) >= 2 and args[:2] in (("queue", "claim"), ("queue", "claim-next")) and "--request-id" not in args:
            self.claim_counter += 1
            args = (*args, "--request-id", f"test-request-{self.claim_counter:08d}")
        result = subprocess.run(
            ["python3", str(SCRIPT), "--root", str(self.root), *cli(*args)],
            text=True, capture_output=True, check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def item(self, item_id, scopes, dependencies=(), tracker="TCK001"):
        path = self.root / ".agents/queue/items" / f"{item_id}.json"
        path.write_text(json.dumps({
            "id": item_id, "tracker": tracker, "title": item_id,
            "status": "READY", "dependencies": list(dependencies),
            "scopes": scopes, "evidence": None,
        }))
        return path

    def tracker_doc(self, name="TCK001.md"):
        path = self.root / "docs/tracking" / name
        path.write_text("# Workset\n\nStatus: PLANNED\n\n## Evidence\n")
        return path

    def checklist_tracker(self):
        path = self.tracker_doc()
        path.write_text(
            "# Workset\n\nStatus: PLANNED\n\n## Acceptance criteria\n\n"
            "- [ ] AC-01: acceptance\n\n## Tasks\n\n- [ ] TASK-01: task\n\n## Evidence\n"
        )
        return path

    def test_cancelled_ids_cannot_be_reused_or_claimed(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        retired = self.root / ".agents/queue/retired"
        retired.mkdir()
        (retired / "Q0001.txt").write_text(json.dumps({"id": "Q0001", "status": "CANCELLED"}))
        self.run_cli("check")
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "worker", success=False)
        self.item("Q0001", ["area:old"])
        result = self.run_cli("check", success=False)
        self.assertIn("cancelled queue id reused", result.stderr)

    def test_indented_and_alternate_checklists_block_done(self):
        self.run_cli("configure", "tracker")
        for prefix in ("  -", "\t-", "*", "+", "1.", "2)"):
            with self.subTest(prefix=prefix):
                path = self.checklist_tracker()
                path.write_text(path.read_text().replace("- [ ]", prefix + " [ ]"))
                before = path.read_bytes()
                self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE",
                             "--evidence", "review passed", success=False)
                self.assertEqual(path.read_bytes(), before)
                path.write_text(path.read_text().replace("Status: PLANNED", "Status: DONE") + "\n- review passed\n")
                self.run_cli("check", success=False)
                path.write_text(path.read_text().replace("[ ]", "[x]"))
                self.run_cli("check")

    def test_unrelated_runtime_dependency_symlink_does_not_block_queue_operations(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / "preserve.txt"
            target.write_text("preserve")
            tools = self.root / ".agent-runtime/tools"
            tools.mkdir()
            link = tools / "node_modules"
            link.symlink_to(external, target_is_directory=True)
            self.run_cli("configure", "full")
            self.run_cli("check")
            self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "worker")
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_text(), "preserve")

    def test_symlinked_claim_file_is_rejected_without_touching_external_data(self):
        self.run_cli("configure", "full")
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / "claim.json"
            target.write_text("preserve")
            claims = self.root / ".agent-runtime/claims"
            claims.mkdir()
            (claims / "Q0001.json").symlink_to(target)
            self.run_cli("queue", "list", success=False)
            self.assertEqual(target.read_text(), "preserve")

    def test_symlinked_runtime_and_lock_are_rejected(self):
        self.run_cli("configure", "standard")
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)
            runtime = self.root / ".agent-runtime"
            (runtime / "queue.lock").unlink()
            runtime.rmdir()
            runtime.symlink_to(outside, target_is_directory=True)
            self.run_cli("configure", "standard", success=False)
            self.assertEqual(list(outside.iterdir()), [])
            runtime.unlink()
            runtime.mkdir()
            target = outside / "lock"
            target.write_text("preserve")
            (runtime / "queue.lock").symlink_to(target)
            self.run_cli("configure", "standard", success=False)
            self.assertEqual(target.read_text(), "preserve")

    def test_symlinked_claims_cannot_delete_external_files(self):
        self.run_cli("configure", "full")
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)
            target = outside / "Q0001.json"
            target.write_text(json.dumps({"id": "Q0001", "agent": "one", "token": "dummy",
                                          "request_id": "expired-request-0001", "expires_at": 0}))
            before = target.read_bytes()
            (self.root / ".agent-runtime/claims").symlink_to(outside, target_is_directory=True)
            self.run_cli("queue", "list", success=False)
            self.assertEqual(target.read_bytes(), before)

    def test_symlinked_tracking_parent_and_item_are_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)
            (self.root / "docs").symlink_to(outside, target_is_directory=True)
            self.run_cli("configure", "tracker", success=False)
            self.assertEqual(list(outside.iterdir()), [])
            (self.root / "docs").unlink()
            self.run_cli("configure", "full")
            self.tracker_doc()
            item = self.item("Q0001", ["area:api"])
            target = outside / "Q0001.json"
            target.write_bytes(item.read_bytes())
            item.unlink()
            item.symlink_to(target)
            self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one", success=False)
            self.assertFalse((self.root / ".agent-runtime/claims/Q0001.json").exists())

    def test_duplicate_tracker_ids_are_rejected_in_all_tracking_modes(self):
        for mode in ("tracker", "full"):
            with self.subTest(mode=mode):
                self.run_cli("configure", mode)
                self.tracker_doc("TCK001.md")
                self.tracker_doc("TCK001-other.md")
                result = self.run_cli("check", success=False)
                self.assertIn("duplicate tracker", result.stderr)
                (self.root / "docs/tracking/TCK001-other.md").unlink()

    def test_archived_tracker_ids_cannot_be_reused(self):
        self.run_cli('configure', 'tracker')
        history = self.root / 'docs/history/agent-workflow/nested'
        history.mkdir(parents=True)
        for name in ('TCK001.txt', 'TCK001-old.md', 'TCK001-closed.txt'):
            path = history / name
            path.write_text('historical evidence')
            result = self.run_cli('tracker', 'new', '--id', 'TCK001', '--title', 'replacement', success=False)
            self.assertIn('reserved by history', result.stderr)
            self.assertFalse((self.root / 'docs/tracking/TCK001.md').exists())
            self.assertEqual(path.read_text(), 'historical evidence')
            path.unlink()
        (history / 'TCK0010-other.txt').write_text('different id')
        self.run_cli('tracker', 'new', '--id', 'TCK001', '--title', 'replacement')

    def test_failed_tracker_status_is_supported(self):
        self.run_cli("configure", "tracker")
        self.tracker_doc()
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "FAILED", "--evidence", "test failure")
        self.run_cli("check")
        self.assertIn("Status: FAILED", (self.root / "docs/tracking/TCK001.md").read_text())

    def test_a_status_line_with_a_note_names_the_line_and_the_convention(self):
        # asdw-harness: `Status: DONE — note` failed mode check with only "invalid tracker status: <path>".
        self.run_cli("configure", "tracker")
        path = self.tracker_doc()
        path.write_text("# Workset\n\nStatus: BLOCKED — waiting on review\n\n## Evidence\n")
        for args in (("check",), ("tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS")):
            with self.subTest(args=args):
                result = self.run_cli(*args, success=False)
                self.assertIn("TCK001.md:3", result.stderr)
                self.assertIn("Status: BLOCKED — waiting on review", result.stderr)
                self.assertIn("Status note:", result.stderr)
        self.assertIn("Status: BLOCKED — waiting", path.read_text())

    def test_tracker_status_accepts_what_check_accepts(self):
        # Review: a valid Status line beside an example line starting with "Status:" passes check, so
        # tracker status must update it too, and an unknown state must stay repairable.
        self.run_cli("configure", "tracker")
        path = self.tracker_doc()
        path.write_text("# Workset\n\nStatus: PLANNED\n\n```\nStatus: <STATE>\n```\n\n## Evidence\n")
        self.run_cli("check")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS")
        path.write_text("# Workset\n\nStatus: FOO\n\n## Evidence\n")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "PLANNED")
        self.run_cli("check")

    def test_execution_selection_survives_mode_upgrade(self):
        self.run_cli("configure", "standard", "--execution", "delegated")
        self.run_cli("configure", "tracker")
        self.assertEqual(json.loads(self.run_cli("show").stdout)["execution"], "delegated")
        self.run_cli("configure", "tracker", "--execution", "direct")
        self.assertEqual(json.loads(self.run_cli("show").stdout)["execution"], "direct")

    def test_invalid_execution_is_rejected(self):
        (self.root / ".lean/config.json").write_text('{"mode":"standard","configured":true,"execution":"parallel"}')
        self.run_cli("check", success=False)

    def test_completion_rechecks_new_dependencies_without_losing_claim(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        path = self.item("Q0001", ["area:api"])
        dependency_path = self.item("Q0002", ["area:prerequisite"])
        claim = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one").stdout)
        item = json.loads(path.read_text())
        item["dependencies"] = ["Q0002"]
        path.write_text(json.dumps(item))
        result = self.run_cli("queue", "complete", "--id", "Q0001", "--token", claim["token"],
                              "--evidence", "focused validation", success=False)
        self.assertIn("dependencies", result.stderr)
        self.assertEqual(json.loads(path.read_text())["status"], "READY")
        claim_path = self.root / ".agent-runtime/claims/Q0001.json"
        self.assertEqual(json.loads(claim_path.read_text())["token"], claim["token"])
        dependency = json.loads(dependency_path.read_text())
        dependency.update(status="DONE", evidence="prerequisite validated")
        dependency_path.write_text(json.dumps(dependency))
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", claim["token"],
                     "--evidence", "focused validation")
        self.run_cli("check")

    def test_check_rejects_done_item_with_unfinished_dependency(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0002", ["area:prerequisite"])
        path = self.item("Q0001", ["area:api"], dependencies=["Q0002"])
        item = json.loads(path.read_text())
        item.update(status="DONE", evidence="manual completion")
        path.write_text(json.dumps(item))
        self.assertIn("dependencies", self.run_cli("check", success=False).stderr)

    def test_standard_is_default_and_has_no_tracking_artifacts(self):
        self.assertIn('"mode": "standard"', self.run_cli("show").stdout)
        self.run_cli("configure", "standard")
        self.run_cli("check")
        self.assertFalse((self.root / "docs/tracking").exists())
        self.run_cli("queue", "claim-next", "--agent", "a", success=False)

    def test_done_requires_a_covering_gate_pass(self):
        self.run_cli("configure", "tracker")
        path = self.checklist_tracker()
        path.write_text(path.read_text().replace("- [ ]", "- [x]"))
        before = path.read_bytes()
        result = self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE",
                              "--evidence", "implementation complete", success=False)
        self.assertIn("gate", result.stderr.lower())
        self.assertEqual(path.read_bytes(), before)

    def test_tracker_creates_documents_without_queue(self):
        self.run_cli("configure", "tracker")
        self.run_cli("check")
        self.assertTrue((self.root / "docs/tracking/TEMPLATE.md").is_file())
        self.run_cli("tracker", "new", "--id", "TCK001", "--title", "Start project")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", success=False)
        tracker_path = self.root / "docs/tracking/TCK001.md"
        tracker_content = tracker_path.read_text().replace("- [ ]", "- [x]")
        tracker_path.write_text(tracker_content)
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", "--evidence", "review passed", "--contract", passing_gate(self.root))
        self.run_cli("check")
        self.assertFalse((self.root / ".agents/queue").exists())
        self.assertIn(".agent-runtime/", (self.root / ".gitignore").read_text())
        self.run_cli("queue", "claim-next", "--agent", "a", success=False)

    def test_done_tracker_requires_evidence_even_after_manual_edit(self):
        self.run_cli("configure", "tracker")
        path = self.tracker_doc()
        path.write_text(path.read_text().replace("Status: PLANNED", "Status: DONE"))
        self.run_cli("check", success=False)

    def test_done_transition_rejects_unchecked_checklist_without_mutation(self):
        self.run_cli("configure", "tracker")
        path = self.checklist_tracker()
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE",
                     "--evidence", "review passed", success=False)
        self.assertIn("Status: PLANNED", path.read_text())
        self.assertNotIn("- review passed", path.read_text())

    def test_new_tracker_template_placeholders_block_done(self):
        self.run_cli("configure", "tracker")
        self.run_cli("tracker", "new", "--id", "TCK001", "--title", "Fresh tracker")
        path = self.root / "docs/tracking/TCK001.md"
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE",
                     "--evidence", "review passed", success=False)
        self.assertIn("Status: PLANNED", path.read_text())

    def test_check_rejects_manually_done_tracker_with_unchecked_checklist(self):
        self.run_cli("configure", "tracker")
        path = self.checklist_tracker()
        path.write_text(path.read_text().replace("Status: PLANNED", "Status: DONE") + "\n- review passed\n")
        self.run_cli("check", success=False)

    def test_completed_checklist_tracker_passes_check(self):
        self.run_cli("configure", "tracker")
        path = self.checklist_tracker()
        content = path.read_text().replace("Status: PLANNED", "Status: DONE").replace("- [ ]", "- [x]")
        path.write_text(content + "\n- review passed\n")
        self.run_cli("check")

    def test_tracker_template_guidance_is_outside_blank_evidence(self):
        template = (TEMPLATES / "tracker.md").read_text()
        evidence = template.split("## Evidence\n", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(evidence.strip(), "")
        self.assertIn("## Evidence guidance", template)

    def test_manual_tracker_template_matches_generated_template(self):
        self.run_cli("configure", "tracker")
        manual_template = (self.root / "docs/tracking/TEMPLATE.md").read_text()
        generated_template = (TEMPLATES / "tracker.md").read_text()
        self.assertEqual(manual_template, generated_template)

    def test_upgrade_preserves_documents_and_forbids_implicit_downgrade(self):
        self.run_cli("configure", "tracker")
        readme = self.root / "docs/tracking/README.md"
        readme.write_text("custom\n")
        self.run_cli("configure", "full")
        self.run_cli("check")
        self.assertEqual(readme.read_text(), "custom\n")
        self.assertTrue((self.root / ".agents/queue/items/.gitkeep").is_file())
        self.assertIn(".agent-runtime/", (self.root / ".gitignore").read_text())
        self.run_cli("configure", "standard", success=False)
        self.assertEqual(json.loads((self.root / ".lean/config.json").read_text())["mode"], "full")

    def test_full_claim_dependencies_scopes_and_completion(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        self.item("Q0002", ["area:api"])
        self.item("Q0003", ["area:web"], dependencies=["Q0001"])
        self.run_cli("check")
        first = json.loads(self.run_cli("queue", "claim-next", "--agent", "one").stdout)
        self.assertEqual(first["id"], "Q0001")
        self.run_cli("queue", "claim-next", "--agent", "two", success=False)
        self.run_cli("queue", "heartbeat", "--id", "Q0001", "--token", "wrong", success=False)
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", first["token"],
                     "--evidence", "", success=False)
        self.run_cli("queue", "heartbeat", "--id", "Q0001", "--token", first["token"])
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", first["token"],
                     "--evidence", "focused validation passed")
        self.assertFalse((self.root / ".agent-runtime/claims/Q0001.json").exists())
        self.assertEqual(json.loads((self.root / ".agents/queue/items/Q0001.json").read_text())["status"], "DONE")
        second = json.loads(self.run_cli("queue", "claim-next", "--agent", "two").stdout)
        self.assertEqual(second["id"], "Q0002")
        third = json.loads(self.run_cli("queue", "claim-next", "--agent", "three").stdout)
        self.assertEqual(third["id"], "Q0003")
        self.run_cli("queue", "release", "--id", "Q0002", "--token", second["token"])
        self.assertFalse((self.root / ".agent-runtime/claims/Q0002.json").exists())

    def test_path_scopes_block_equal_ancestor_and_alias_claims(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        pairs = (
            ("src", "src"), ("src/", "src/a.ts"), ("src/a.ts", "src"),
            ("src", "src/"), ("./src//", "src/a.ts"),
            ("src/lib/../a.ts", "src/a.ts"), ("src\\lib", "src/lib/a.ts"),
            (".", "src/a.ts"), ("src", "."), ("src/..", "docs"),
            ("area:api", "area:api"),
        )
        for held, candidate in pairs:
            for action in ("claim", "claim-next"):
                with self.subTest(held=held, candidate=candidate, action=action):
                    self.item("Q0001", [held])
                    self.item("Q0002", [candidate])
                    self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one")
                    args = ("queue", action, "--agent", "two")
                    if action == "claim":
                        args += ("--id", "Q0002")
                    try:
                        result = self.run_cli(*args, success=False)
                        self.assertIn("no claimable queue item", result.stderr)
                        self.assertFalse((self.root / ".agent-runtime/claims/Q0002.json").exists())
                    finally:
                        # Keep each parameter case independent even before the fix.
                        for path in (self.root / ".agent-runtime/claims").glob("*.json"):
                            claim = json.loads(path.read_text())
                            self.run_cli("queue", "release", "--id", claim["id"], "--token", claim["token"])

    def test_path_scopes_allow_siblings_and_distinct_opaque_labels(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        pairs = (
            ("src", "src-other/a.ts"), ("src/a.ts", "src/b.ts"),
            ("src/A.ts", "src/a.ts"), ("area:api", "area:api/v2"),
            ("area:api/../web", "area:web"), ("area:api", "area:web"),
            ("area:api", "."), ("C:src", "C:src/a.ts"),
            ("area:api/*", "area:api/a.ts"),
        )
        for held, candidate in pairs:
            for action in ("claim", "claim-next"):
                with self.subTest(held=held, candidate=candidate, action=action):
                    self.item("Q0001", [held])
                    self.item("Q0002", [candidate])
                    first = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one").stdout)
                    args = ("queue", action, "--agent", "two")
                    if action == "claim":
                        args += ("--id", "Q0002")
                    second = json.loads(self.run_cli(*args).stdout)
                    self.assertEqual(second["id"], "Q0002")
                    self.run_cli("check")
                    for claim in (first, second):
                        self.run_cli("queue", "release", "--id", claim["id"], "--token", claim["token"])

    def test_unsafe_path_scopes_are_rejected_before_claiming(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        for scope in ("", " ", "/src", "\\src", "C:/src", "C:\\src", "//server/src", "../src",
                      "src/../../outside", "src/*", "src/?.ts", "src/[ab].ts", "src\x00file"):
            self.item("Q0001", [scope])
            for args in (("check",), ("queue", "claim", "--id", "Q0001", "--agent", "one"),
                         ("queue", "claim-next", "--agent", "one")):
                with self.subTest(scope=scope, args=args):
                    try:
                        result = self.run_cli(*args, success=False)
                        self.assertIn("invalid path scope", result.stderr)
                        self.assertFalse((self.root / ".agent-runtime/claims/Q0001.json").exists())
                    finally:
                        path = self.root / ".agent-runtime/claims/Q0001.json"
                        if path.exists():
                            claim = json.loads(path.read_text())
                            self.run_cli("queue", "release", "--id", "Q0001", "--token", claim["token"])

    def test_path_scope_claim_next_skips_conflicts_and_preserves_lease_lifecycle(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["src/"])
        self.item("Q0002", ["src/a.ts"])
        self.item("Q0003", ["docs"])
        first = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one",
                                        "--request-id", "path-retry-0001").stdout)
        for action in ("claim", "claim-next"):
            args = ("queue", action, "--agent", "one", "--request-id", "path-retry-0001")
            if action == "claim":
                args += ("--id", "Q0001")
            self.assertEqual(json.loads(self.run_cli(*args).stdout), first)
        sibling = json.loads(self.run_cli("queue", "claim-next", "--agent", "two").stdout)
        self.assertEqual(sibling["id"], "Q0003")
        path = self.root / ".agent-runtime/claims/Q0001.json"
        path.write_text(json.dumps(dict(first, expires_at=0)))
        child = json.loads(self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "three").stdout)
        self.assertFalse(path.exists())
        self.run_cli("queue", "release", "--id", "Q0002", "--token", child["token"])
        renewed = json.loads(self.run_cli("queue", "claim-next", "--agent", "one").stdout)
        self.assertEqual(renewed["id"], "Q0001")
        self.assertNotEqual(renewed["token"], first["token"])
        self.run_cli("check")

    def test_loaded_path_scope_conflicts_reject_check_list_and_receipt_retry(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["src/"])
        second_item = self.item("Q0002", ["other"])
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one", "--request-id", "scope-retry-0001")
        self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "two")
        claims = sorted((self.root / ".agent-runtime/claims").glob("*.json"))
        before = [path.read_bytes() for path in claims]
        for scope in ("./src//", "src/a.ts", "."):
            self.item("Q0002", [scope])
            for args in (("check",), ("queue", "list"),
                         ("queue", "claim", "--id", "Q0001", "--agent", "one", "--request-id", "scope-retry-0001"),
                         ("queue", "claim-next", "--agent", "one", "--request-id", "scope-retry-0001")):
                with self.subTest(scope=scope, args=args):
                    item_before = second_item.read_bytes()
                    result = self.run_cli(*args, success=False)
                    self.assertIn("overlapping active claim scope", result.stderr)
                    self.assertEqual(second_item.read_bytes(), item_before)
                    self.assertEqual([path.read_bytes() for path in claims], before)

    def test_worker_releases_blocked_item_and_controller_resumes_it(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:contract"])
        self.item("Q0002", ["area:api"], dependencies=["Q0001"])
        self.item("Q0003", ["area:web"])

        first = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "worker-one").stdout)
        # Q0003 is discovered as Q0001's prerequisite after Q0001 was claimed.
        blocked_path = self.root / ".agents/queue/items/Q0001.json"
        blocked_item = json.loads(blocked_path.read_text())
        blocked_item["dependencies"] = ["Q0003"]
        blocked_path.write_text(json.dumps(blocked_item))
        self.run_cli("check")
        self.run_cli("queue", "release", "--id", "Q0001", "--token", first["token"])
        self.assertEqual(json.loads(blocked_path.read_text())["status"], "READY")
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "worker-one", success=False)
        self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "worker-one", success=False)

        other = json.loads(self.run_cli("queue", "claim", "--id", "Q0003", "--agent", "worker-two").stdout)
        self.run_cli("queue", "complete", "--id", "Q0003", "--token", other["token"],
                     "--evidence", "web validation passed")
        resumed = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "worker-one").stdout)
        self.assertNotEqual(resumed["token"], first["token"])
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", resumed["token"],
                     "--evidence", "contract validation passed")
        dependent = json.loads(self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "worker-two").stdout)
        self.run_cli("queue", "complete", "--id", "Q0002", "--token", dependent["token"],
                     "--evidence", "api validation passed")
        self.run_cli("check")
        self.assertEqual(len(list((self.root / ".agent-runtime/claims").glob("*.json"))), 0)

    def test_expired_claim_can_be_reclaimed(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        first = json.loads(self.run_cli("queue", "claim-next", "--agent", "one").stdout)
        claim = self.root / ".agent-runtime/claims/Q0001.json"
        expired = json.loads(claim.read_text())
        expired["expires_at"] = 0
        claim.write_text(json.dumps(expired))
        second = json.loads(self.run_cli("queue", "claim-next", "--agent", "two").stdout)
        self.assertNotEqual(first["token"], second["token"])
        self.run_cli("queue", "heartbeat", "--id", "Q0001", "--token", first["token"], success=False)

    def test_one_agent_cannot_hold_two_claims(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        self.item("Q0002", ["area:web"])
        self.run_cli("queue", "claim-next", "--agent", "one")
        self.run_cli("queue", "claim-next", "--agent", "one", success=False)

    def test_invalid_queue_item_is_rejected(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"], dependencies=["Q0002"])
        self.run_cli("check", success=False)
        self.run_cli("queue", "claim-next", "--agent", "one", success=False)

    def test_named_tracker_document_is_accepted(self):
        self.run_cli("configure", "full")
        self.tracker_doc("TCK001-setup.md")
        self.item("Q0001", ["area:api"])
        self.run_cli("check")
        claim = json.loads(self.run_cli("queue", "claim-next", "--agent", "one").stdout)
        self.assertEqual(claim["id"], "Q0001")

    def test_invalid_item_filename_is_not_silently_skipped(self):
        self.run_cli("configure", "full")
        (self.root / ".agents/queue/items/bad.json").write_text("{}")
        self.run_cli("check", success=False)

    def test_unconfigured_full_is_rejected(self):
        (self.root / ".lean/config.json").write_text('{"mode":"full","configured":false}')
        self.run_cli("queue", "list", success=False)

    def test_exact_claim_selects_assigned_item(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        self.item("Q0002", ["area:web"])
        claim = json.loads(self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "one").stdout)
        self.assertEqual(claim["id"], "Q0002")

    def test_completed_item_with_live_lease_fails_check_and_can_retry_completion(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        path = self.item("Q0001", ["area:api"])
        claim = json.loads(self.run_cli("queue", "claim-next", "--agent", "one").stdout)
        item = json.loads(path.read_text())
        item["status"] = "DONE"
        item["evidence"] = "focused validation passed"
        path.write_text(json.dumps(item))
        self.run_cli("check", success=False)
        self.run_cli("queue", "list", success=False)
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", claim["token"],
                     "--evidence", "focused validation passed")
        self.run_cli("check")

    def test_full_done_tracker_requires_done_queue(self):
        self.run_cli("configure", "full")
        path = self.tracker_doc()
        path.write_text(path.read_text().replace("Status: PLANNED", "Status: DONE").replace("## Evidence\n", "## Evidence\n\n- review passed\n"))
        self.item("Q0001", ["area:api"])
        self.run_cli("check", success=False)
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", "--evidence", "again", success=False)

    def test_unrelated_broken_claim_does_not_block_token_operations(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        first_item = self.item("Q0001", ["area:api"])
        self.item("Q0002", ["area:web"])
        first = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one").stdout)
        second = json.loads(self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "two").stdout)
        item = json.loads(first_item.read_text())
        item["status"] = "DONE"
        item["evidence"] = "validation passed"
        first_item.write_text(json.dumps(item))
        (self.root / ".agent-runtime/claims/bad.json").write_text("{}")
        self.run_cli("queue", "heartbeat", "--id", "Q0002", "--token", second["token"])
        self.run_cli("queue", "release", "--id", "Q0002", "--token", second["token"])
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", first["token"],
                     "--evidence", "validation passed")

    def test_done_item_requires_nonblank_string_evidence(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        path = self.item("Q0001", ["area:api"])
        for evidence in ("   ", {"text": "passed"}):
            item = json.loads(path.read_text())
            item["status"] = "DONE"
            item["evidence"] = evidence
            path.write_text(json.dumps(item))
            self.run_cli("check", success=False)

    def test_invalid_lease_expiry_is_rejected_without_mutation(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        item_path = self.item("Q0001", ["area:api"])
        claim = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one").stdout)
        claim_path = self.root / ".agent-runtime/claims/Q0001.json"
        original_item = item_path.read_bytes()
        for expiry in (float("nan"), float("inf"), float("-inf"), True, 10 ** 400, None, "future"):
            for command in ("check", "release", "heartbeat", "complete"):
                with self.subTest(expiry=expiry, command=command):
                    item_path.write_bytes(original_item)
                    claim_path.write_text(json.dumps(dict(claim, expires_at=expiry)))
                    before = claim_path.read_bytes(), item_path.read_bytes()
                    args = ("check",) if command == "check" else (
                        "queue", command, "--id", "Q0001", "--token", claim["token"])
                    if command == "complete":
                        args += ("--evidence", "tests passed")
                    result = self.run_cli(*args, success=False)
                    self.assertIn("invalid claim", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(before, (claim_path.read_bytes(), item_path.read_bytes()))

    def test_token_operations_reject_malformed_owned_claim(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        item_path = self.item("Q0001", ["area:api"])
        claim = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one").stdout)
        claim_path = self.root / ".agent-runtime/claims/Q0001.json"
        original_item = item_path.read_bytes()
        for field, value in (("agent", ""), ("agent", "   "), ("request_id", "bad"),
                             ("request_id", None), ("token", ""), ("token", "   ")):
            for command in ("release", "heartbeat", "complete"):
                with self.subTest(field=field, command=command):
                    item_path.write_bytes(original_item)
                    claim_path.write_text(json.dumps(dict(claim, **{field: value})))
                    before = claim_path.read_bytes(), item_path.read_bytes()
                    args = ("queue", command, "--id", "Q0001", "--token", value if field == "token" else claim["token"])
                    if command == "complete":
                        args += ("--evidence", "tests passed")
                    self.run_cli(*args, success=False)
                    self.assertEqual(before, (claim_path.read_bytes(), item_path.read_bytes()))

    def test_claim_receipt_retry_revalidates_active_claims(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        item_path = self.item("Q0001", ["area:api"])
        self.item("Q0002", ["area:web"])
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one", "--request-id", "receipt-retry-001")
        self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "two")
        claim_paths = sorted((self.root / ".agent-runtime/claims").glob("*.json"))
        original_claims = [path.read_bytes() for path in claim_paths]
        original = item_path.read_text()
        for changes in ({"status": "DONE", "evidence": "passed"}, {"scopes": ["area:web"]}):
            item_path.write_text(json.dumps(dict(json.loads(original), **changes)))
            for action in ("claim", "claim-next"):
                with self.subTest(changes=changes, action=action):
                    before = item_path.read_bytes()
                    args = ("queue", action, "--agent", "one", "--request-id", "receipt-retry-001")
                    if action == "claim":
                        args += ("--id", "Q0001")
                    self.run_cli(*args, success=False)
                    self.assertEqual(item_path.read_bytes(), before)
                    self.assertEqual([path.read_bytes() for path in claim_paths], original_claims)
        item_path.write_text(original)
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one", "--request-id", "receipt-retry-001")

    def test_lost_claim_receipt_can_be_recovered_with_request_id(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        first = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one",
                                        "--request-id", "request-00000001").stdout)
        retry = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one",
                                        "--request-id", "request-00000001").stdout)
        self.assertEqual(first["token"], retry["token"])
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "one",
                     "--request-id", "request-00000002", success=False)
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "two",
                     "--request-id", "request-00000001", success=False)

    def test_context_command_in_standard_and_tracker_modes(self):
        # In unconfigured standard mode
        res = self.run_cli("context")
        data = json.loads(res.stdout)
        self.assertEqual(data["mode"], "standard")
        self.assertEqual(data["execution"], "direct")
        self.assertFalse(data["configured"])
        self.assertIsNone(data["active_tracker"])

        # Switch to tracker mode and create an active tracker
        self.run_cli("configure", "tracker")
        self.tracker_doc("TCK001.md")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS")
        res2 = self.run_cli("context")
        data2 = json.loads(res2.stdout)
        self.assertEqual(data2["mode"], "tracker")
        self.assertIsNotNone(data2["active_tracker"])
        self.assertEqual(data2["active_tracker"]["id"], "TCK001")
        self.assertEqual(data2["active_tracker"]["status"], "IN_PROGRESS")

    def test_tracker_archive_dry_run_and_apply(self):
        self.run_cli("configure", "tracker")
        doc = self.checklist_tracker()
        doc.write_text(doc.read_text().replace("- [ ]", "- [x]"))
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", "--evidence", "all done", "--contract", passing_gate(self.root))

        # Dry run does not move the file
        dry = self.run_cli("tracker", "archive", "--dry-run")
        dry_data = json.loads(dry.stdout)
        self.assertIn("TCK001", dry_data["selected"])
        self.assertFalse(dry_data["applied"])
        self.assertTrue((self.root / "docs/tracking/TCK001.md").is_file())

        # Apply moves to docs/history/agent-workflow
        applied = self.run_cli("tracker", "archive", "--apply")
        app_data = json.loads(applied.stdout)
        self.assertIn("TCK001", app_data["archived"])
        self.assertTrue(app_data["applied"])
        self.assertFalse((self.root / "docs/tracking/TCK001.md").exists())
        self.assertTrue((self.root / "docs/history/agent-workflow/TCK001.md").is_file())

        # History is checked and integrity holds
        self.run_cli("check")

    def done_tracker(self, tracker_id):
        """A valid DONE tracker created through the CLI (tracker mode)."""
        self.tracker_doc(f"{tracker_id}.md")
        self.run_cli("tracker", "status", "--id", tracker_id, "--status", "DONE", "--evidence", "validated", "--contract", passing_gate(self.root))
        return self.root / "docs/tracking" / f"{tracker_id}.md"

    def snapshot(self):
        files = (p for p in self.root.rglob("*") if p.is_file())
        return {str(p.relative_to(self.root)): p.read_bytes() for p in files
                if p.relative_to(self.root).parts[0] != ".git"}

    def test_archive_refuses_invalid_done_tracker_instead_of_hiding_it(self):
        self.run_cli("configure", "tracker")
        doc = self.checklist_tracker()
        doc.write_text(doc.read_text().replace("Status: PLANNED", "Status: DONE"))
        self.run_cli("check", success=False)
        result = self.run_cli("tracker", "archive", "--apply", success=False)
        self.assertIn("DONE tracker without evidence", result.stderr)
        self.assertTrue(doc.is_file())
        self.assertFalse((self.root / "docs/history").exists())
        self.run_cli("check", success=False)

    def test_full_mode_archive_requires_linked_done_items_and_keeps_links(self):
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        claim = json.loads(self.run_cli("queue", "claim-next", "--agent", "one").stdout)
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", claim["token"], "--evidence", "validated")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", "--evidence", "validated", "--contract", passing_gate(self.root))
        orphan = self.tracker_doc("TCK002.md")
        orphan.write_text("# Orphan\n\nStatus: DONE\n\n## Evidence\n\n- manual\n")
        result = self.run_cli("tracker", "archive", "--apply", success=False)
        self.assertIn("DONE tracker has unfinished queue items: TCK002", result.stderr)
        self.assertTrue((self.root / "docs/tracking/TCK001.md").is_file())
        orphan.unlink()
        data = json.loads(self.run_cli("tracker", "archive", "--apply").stdout)
        self.assertEqual(data["archived"], ["TCK001"])
        self.run_cli("check")  # Q0001 still resolves its archived tracker.
        self.run_cli("queue", "list")
        result = self.run_cli("tracker", "new", "--id", "TCK001", "--title", "reuse", success=False)
        self.assertIn("reserved by history", result.stderr)

    def test_archived_tracker_is_read_only(self):
        self.run_cli("configure", "tracker")
        self.done_tracker("TCK001")
        self.run_cli("tracker", "archive", "--apply")
        archived = self.root / "docs/history/agent-workflow/TCK001.md"
        before = archived.read_bytes()
        result = self.run_cli("tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS", success=False)
        self.assertIn("archived and read-only", result.stderr)
        self.assertEqual(archived.read_bytes(), before)

    def test_archive_rejects_a_symlinked_history_directory(self):
        self.run_cli("configure", "tracker")
        doc = self.done_tracker("TCK001")
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (self.root / "docs/history").mkdir(parents=True)
        (self.root / "docs/history/agent-workflow").symlink_to(outside.name)
        result = self.run_cli("tracker", "archive", "--apply", success=False)
        self.assertIn("must not be a symlink", result.stderr)
        self.assertTrue(doc.is_file())
        self.assertEqual(list(Path(outside.name).iterdir()), [])

    def test_archive_checks_every_destination_and_id_before_moving(self):
        self.run_cli("configure", "tracker")
        first = self.done_tracker("TCK001")
        self.done_tracker("TCK002")
        older = self.root / "docs/history/agent-workflow/2025"
        older.mkdir(parents=True)
        (older / "TCK002-old.md").write_text("# Old\n\nStatus: DONE\n")
        result = self.run_cli("tracker", "archive", "--apply", success=False)
        self.assertIn("tracker id already archived: TCK002", result.stderr)
        self.assertTrue(first.is_file())
        self.assertFalse((self.root / "docs/history/agent-workflow/TCK001.md").exists())

    def test_archive_keeps_a_takeover_original_next_to_its_active_tracker(self):
        self.run_cli("configure", "tracker")
        self.done_tracker("TCK001")
        history = self.root / "docs/history/agent-workflow"
        history.mkdir(parents=True)
        original = history / "TCK001.txt"  # takeover keeps a migrated tracker's original here.
        original.write_text("foreign original")
        self.run_cli("check")
        data = json.loads(self.run_cli("tracker", "archive", "--apply").stdout)
        self.assertEqual(data["archived"], ["TCK001"])
        self.assertEqual(original.read_text(), "foreign original")
        self.assertTrue((history / "TCK001.md").is_file())

    def test_archive_by_id(self):
        self.run_cli("configure", "tracker")
        self.done_tracker("TCK001")
        self.done_tracker("TCK002")
        self.tracker_doc("TCK003.md")
        data = json.loads(self.run_cli("tracker", "archive", "--id", "TCK002", "--apply").stdout)
        self.assertEqual(data["archived"], ["TCK002"])
        self.assertTrue((self.root / "docs/tracking/TCK001.md").is_file())
        self.assertIn("already archived", self.run_cli("tracker", "archive", "--id", "TCK002", "--apply",
                                                       success=False).stderr)
        self.assertIn("only DONE trackers", self.run_cli("tracker", "archive", "--id", "TCK003", "--dry-run",
                                                         success=False).stderr)
        self.assertIn("invalid tracker id", self.run_cli("tracker", "archive", "--id", "../TCK001", "--apply",
                                                         success=False).stderr)
        self.assertIn("found 0", self.run_cli("tracker", "archive", "--id", "TCK999", "--apply",
                                              success=False).stderr)

    def test_context_is_read_only_and_reports_git_and_gate(self):
        (self.root / ".gitignore").write_text(".env\n.agent-runtime/\n")
        self.run_cli("configure", "full")
        self.tracker_doc()
        self.item("Q0001", ["area:api"])
        self.run_cli("queue", "claim-next", "--agent", "one")
        claim = self.root / ".agent-runtime/claims/Q0001.json"
        expired = json.loads(claim.read_text())
        expired["expires_at"] = 0
        claim.write_text(json.dumps(expired))
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        before = self.snapshot()
        index = self.root / ".git/index"
        data = json.loads(self.run_cli("context").stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(claim.is_file())  # An expired claim is reported, never cleaned up.
        self.assertFalse(index.exists())  # git status did not write an index.
        self.assertEqual(data["active_claims"], [])
        self.assertEqual(data["git"]["status"], "modified")
        self.assertIn("docs/", data["git"]["untracked"])
        self.assertEqual(data["gate"]["status"], "NOT_RUN")
        # The report names the shared result source and remains read-only.
        self.assertIn("shared gate results in workflow_root", data["gate"]["source"])

        markers = self.root / ".agent-runtime"
        (markers / "gate-failed").write_text("c1")
        self.assertEqual(json.loads(self.run_cli("context").stdout)["gate"]["status"], "CONTRACT_REFUSED")
        (markers / "gate-failed").write_text("2")
        self.assertEqual(json.loads(self.run_cli("context").stdout)["gate"]["status"], "FAIL")
        (markers / "gate-failed").unlink()
        (markers / "gate-cache").write_text("0" * 64)
        self.assertEqual(json.loads(self.run_cli("context").stdout)["gate"]["status"], "STALE")
        state = subprocess.run(["python3", str(SCRIPT), "--root", str(self.root), "evidence", "gate-state"],
                               text=True, capture_output=True, check=True).stdout.strip()
        (markers / "gate-cache").write_text(state)
        self.assertEqual(json.loads(self.run_cli("context").stdout)["gate"]["status"], "PASS")


class QueueTrackerLookupTests(unittest.TestCase):
    """Queue validation scales with records while keeping exact, fresh tracker linkage."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("docs/tracking", "docs/history/agent-workflow/2026", ".agents/queue/items"):
            (self.root / name).mkdir(parents=True)
        self.workflow = workflow

    def tracker(self, name="TCK001.md", archived=False):
        directory = "docs/history/agent-workflow/2026" if archived else "docs/tracking"
        path = self.root / directory / name
        path.write_text("# Workset\nStatus: PLANNED\n")
        return path

    def item(self, number=1, tracker="TCK001"):
        value = {"id": f"Q{number:04d}", "tracker": tracker, "title": "Task", "status": "READY",
                 "scopes": [f"area:{number}"], "dependencies": [], "evidence": None}
        (self.root / ".agents/queue/items" / f"Q{number:04d}.json").write_text(json.dumps(value))
        return value

    def test_queue_enumerates_tracker_directories_once_per_validation(self):
        self.tracker()
        self.tracker("TCK002-task.md")
        self.tracker("TCK003-task.md", archived=True)
        expected = {}
        for n in range(1, 13):
            item = self.item(n, f"TCK{n % 3 + 1:03d}")
            expected[item["id"]] = item
        active, history = [], []
        glob, rglob = Path.glob, Path.rglob

        def count_active(path, *args, **kwargs):
            if path == self.root / "docs/tracking":
                active.append(args[0])
            return glob(path, *args, **kwargs)

        def count_history(path, *args, **kwargs):
            if path == self.root / "docs/history/agent-workflow":
                history.append(args[0])
            return rglob(path, *args, **kwargs)

        with mock.patch.object(Path, "glob", count_active), mock.patch.object(Path, "rglob", count_history):
            self.assertEqual(self.workflow.items(self.root), expected)
        # Deterministic I/O bound, not a host-dependent wall-clock threshold.
        self.assertLessEqual(len(active), 1, active)
        self.assertLessEqual(len(history), 1, history)

    def test_sparse_queue_stats_only_referenced_tracker_documents(self):
        self.tracker()
        self.tracker("TCK002-task.md", archived=True)
        for number in range(3, 103):
            self.tracker(f"TCK{number:03d}-unrelated.md", archived=True)
        expected = {item["id"]: item for item in (self.item(), self.item(2, "TCK002"))}
        checked = []
        is_file = Path.is_file

        def count_documents(path):
            if path.suffix == ".md" and path.name.startswith("TCK"):
                checked.append(path.name)
            return is_file(path)

        with mock.patch.object(Path, "is_file", count_documents):
            self.assertEqual(self.workflow.items(self.root), expected)
        self.assertCountEqual(checked, ["TCK001.md", "TCK002-task.md"])

    def test_queue_lookup_includes_archived_queue_sources(self):
        self.tracker()
        self.tracker("TCK002-task.md", archived=True)
        current = self.item()
        archived = self.item(2, "TCK002")
        archived.update(status="DONE", evidence="checked")
        with mock.patch.object(self.workflow, "queue_history", return_value={
                "Q0002": {"content": json.dumps(archived)}}):
            (self.root / ".agents/queue/items/Q0002.json").unlink()
            self.assertEqual(self.workflow.items(self.root), {"Q0001": current, "Q0002": archived})
            self.tracker("TCK002-duplicate.md")
            with self.assertRaisesRegex(ValueError, "expected one tracker document for TCK002, found 2"):
                self.workflow.items(self.root)

    def test_queue_lookup_preserves_first_item_error_before_later_invalid_tracker(self):
        self.item()
        self.item(2, tracker=["invalid"])
        with self.assertRaisesRegex(ValueError, "expected one tracker document for TCK001, found 0"):
            self.workflow.items(self.root)

    def test_queue_resolves_nested_archive_and_ignores_original_text(self):
        self.tracker("TCK001-original.txt")
        self.tracker("TCK001-task.md", archived=True)
        self.tracker("TCK0010-other.md")
        item = self.item()
        self.assertEqual(self.workflow.items(self.root), {item["id"]: item})

    def test_queue_requires_exact_id_and_a_document(self):
        self.tracker("TCK0010-other.md")
        self.tracker("TCK001-original.txt", archived=True)
        (self.root / "docs/tracking/TCK001.md").mkdir()
        self.item()
        with self.assertRaisesRegex(ValueError, "expected one tracker document for TCK001, found 0"):
            self.workflow.items(self.root)

    def test_queue_rejects_active_and_archived_duplicates(self):
        self.tracker()
        self.item()
        for archived in (False, True):
            with self.subTest(archived=archived):
                duplicate = self.tracker("TCK001-other.md", archived=archived)
                try:
                    with self.assertRaisesRegex(ValueError, "expected one tracker document for TCK001, found 2"):
                        self.workflow.items(self.root)
                finally:
                    duplicate.unlink()

    def test_queue_refreshes_lookup_after_a_move_deletion_and_addition(self):
        active = self.tracker()
        item = self.item()
        self.assertEqual(self.workflow.items(self.root), {item["id"]: item})
        archived = self.root / "docs/history/agent-workflow/2026/TCK001-task.md"
        active.rename(archived)
        self.assertEqual(self.workflow.items(self.root), {item["id"]: item})
        archived.unlink()
        with self.assertRaisesRegex(ValueError, "found 0"):
            self.workflow.items(self.root)
        self.tracker()
        self.assertEqual(self.workflow.items(self.root), {item["id"]: item})
        self.tracker("TCK001-second.md", archived=True)
        with self.assertRaisesRegex(ValueError, "found 2"):
            self.workflow.items(self.root)

    def test_queue_lookup_does_not_leak_between_roots(self):
        self.tracker()
        self.item()
        self.assertEqual(len(self.workflow.items(self.root)), 1)
        other = self.root / "other"
        (other / ".agents/queue/items").mkdir(parents=True)
        source = self.root / ".agents/queue/items/Q0001.json"
        (other / ".agents/queue/items/Q0001.json").write_bytes(source.read_bytes())
        with self.assertRaisesRegex(ValueError, "found 0"):
            self.workflow.items(other)

    def test_queue_skips_tracker_scan_until_basic_item_validation_passes(self):
        with mock.patch.object(self.workflow, "tracker_document_counts") as index:
            self.assertEqual(self.workflow.items(self.root), {})
            item = self.item(tracker="invalid")
            with self.assertRaisesRegex(ValueError, "invalid tracker: Q0001"):
                self.workflow.items(self.root)
            item["tracker"] = "TCK001"
            item["title"] = ""
            (self.root / ".agents/queue/items/Q0001.json").write_text(json.dumps(item))
            with self.assertRaisesRegex(ValueError, "missing title: Q0001"):
                self.workflow.items(self.root)
            index.assert_not_called()

    def test_queue_counts_duplicates_in_separate_archive_directories(self):
        self.tracker(archived=True)
        nested = self.root / "docs/history/agent-workflow/2025/nested"
        nested.mkdir(parents=True)
        (nested / "TCK001-another.md").write_text("# Workset\n")
        self.item()
        with self.assertRaisesRegex(ValueError, "expected one tracker document for TCK001, found 2"):
            self.workflow.items(self.root)

    def test_queue_ignores_nested_active_trackers_and_non_hyphen_suffixes(self):
        nested = self.root / "docs/tracking/nested"
        nested.mkdir()
        (nested / "TCK001.md").write_text("# Workset\n")
        self.tracker("TCK001.other.md")
        self.item()
        with self.assertRaisesRegex(ValueError, "expected one tracker document for TCK001, found 0"):
            self.workflow.items(self.root)
        self.tracker("TCK001-.md", archived=True)
        self.assertEqual(len(self.workflow.items(self.root)), 1)


if __name__ == "__main__":
    unittest.main()
