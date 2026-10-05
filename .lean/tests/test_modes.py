"""Behavior checks for repository modes and full-mode queue ownership."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflow.py"
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


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
            ["python3", str(SCRIPT), "--root", str(self.root), *args],
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

    def test_failed_tracker_status_is_supported(self):
        self.run_cli("configure", "tracker")
        self.tracker_doc()
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "FAILED", "--evidence", "test failure")
        self.run_cli("check")
        self.assertIn("Status: FAILED", (self.root / "docs/tracking/TCK001.md").read_text())

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

    def test_tracker_creates_documents_without_queue(self):
        self.run_cli("configure", "tracker")
        self.run_cli("check")
        self.assertTrue((self.root / "docs/tracking/TEMPLATE.md").is_file())
        self.run_cli("tracker", "new", "--id", "TCK001", "--title", "Start project")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", success=False)
        tracker_path = self.root / "docs/tracking/TCK001.md"
        tracker_content = tracker_path.read_text().replace("- [ ]", "- [x]")
        tracker_path.write_text(tracker_content)
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", "--evidence", "review passed")
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


if __name__ == "__main__":
    unittest.main()
