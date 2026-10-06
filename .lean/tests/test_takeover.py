"""Observable migration boundaries and crash recovery in isolated repositories."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/takeover.py"
spec = importlib.util.spec_from_file_location("takeover", SCRIPT)
TOOL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TOOL)


class TakeoverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lean takeover ")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "dirty target"
        self.source = self.base / "baseline"
        self.session = self.base / "private session"
        self.root.mkdir()
        self.source.mkdir()
        for name in (".lean/policy", ".lean/templates", ".lean/scripts", ".lean/tests",
                     ".claude/skills", ".claude/hooks", ".claude/agents", ".agents/skills"):
            (self.source / name).mkdir(parents=True)
        for name in ("AGENTS.md", "CLAUDE.md", ".lean/README.md", ".lean/CUSTOMIZING.md",
                     ".lean/CHANGELOG.md", ".lean/LICENSE"):
            (self.source / name).write_text("Portable rules\n## Project additions\nSource project-only text\n")
        registry = ["AGENTS.md", "CLAUDE.md", ".lean/README.md", ".lean/CUSTOMIZING.md",
                    ".lean/CHANGELOG.md", ".lean/LICENSE", ".lean/assets.json"]
        (self.source / ".lean/assets.json").write_text(json.dumps({"schema": 1, "files": registry}))
        (self.source / ".lean/PROJECT.md").write_text("SOURCE FACTS MUST NOT IMPORT\n")
        (self.source / ".lean/config.json").write_text('{"mode":"full"}')
        (self.source / ".claude/settings.json").write_text('{"permissions":{"allow":["ALL"]}}')
        (self.root / "AGENTS.md").write_text("Dirty original: preserve business rules\n")
        (self.root / "AGENTS.md").chmod(0o640)
        (self.root / ".env").write_text("DO_NOT_READ_OR_COPY\n")
        (self.root / "application.txt").write_text("unrelated pending work\n")

    def init(self):
        TOOL.initial(self.root, self.session)
        return TOOL.load(self.session / "inventory.json")

    def prepare(self, new_file=True):
        manifest = self.init()
        for name, entry in list(manifest["files"].items()):
            if entry["status"] == "unread":
                TOOL.coverage(self.session, manifest, self.root, name, "cover", entry["before"]["sha256"])
        TOOL.draft(self.session, manifest, self.root, self.source)
        plan = TOOL.load(self.session / "plan.json")
        plan["unresolved"] = []
        plan["acceptance"] = ["Project rules preserved; target checks and HIGH review pass"]
        plan["decisions"] = [{"id": "D1", "choice": "Retain business rule", "evidence": "fixture user answer"}]
        plan["rule_map"] = [{"source": "AGENTS.md", "rule": "preserve business rules",
                             "destination": "AGENTS.md Project additions", "reason": "accepted requirement"}]
        for op in plan["operations"]:
            if op["path"] == "AGENTS.md":
                op["content"] += "Preserve business rules\n"
        if new_file:
            plan["operations"].append({"path": "new/deep.txt", "before": None, "content": "new document\n",
                                       "mode": 0o644, "reason": "document migration"})
        paths = {op["path"] for op in plan["operations"]}
        plan["dispositions"] = [{"path": name, "action": "replace" if name in paths else "keep", "reason": "fixture mapping"}
                                for name, entry in manifest["files"].items() if entry["status"] == "read"]
        TOOL.save(self.session / "plan.json", plan)
        receipt = self.seal_ready(manifest, "fixture user accepted concrete diff")
        return manifest, plan, receipt

    def seal_ready(self, manifest, evidence, session=None, real_checks=False):
        session = session or self.session
        staged = TOOL.stage(session, manifest, self.root)
        directory = Path(staged["directory"])
        if real_checks:
            subprocess.run(["git", "init", "-q", str(directory)], check=True)
            for command in (["bash", ".lean/scripts/check-structure.sh"], ["python3", ".lean/scripts/workflow.py", "check"]):
                result = subprocess.run(command, cwd=directory, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            validation = "Fixture staging: actual structure and mode checks passed; application gate is true"
        else:
            validation = "Fixture staging: content/mode fingerprints checked; synthetic baseline has no runnable gate"
        TOOL.stage_check(session, manifest, self.root, validation)
        return TOOL.seal(session, manifest, self.root, evidence)

    def apply(self, manifest, receipt):
        return TOOL.apply_plan(self.session, manifest, self.root, receipt["plan_sha256"])

    def cli(self, *args, success=True):
        result = subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 2, result.stdout + result.stderr)
        return result

    def test_inventory_is_read_only_and_secrets_are_not_hashed(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text(".claude/\n")
        (self.root / ".claude").mkdir()
        (self.root / ".claude/custom.md").write_text("Ignored but active workflow\n")
        (self.root / "sub").mkdir()
        (self.root / "sub/AGENTS.md").write_text("Nested rules\n")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        real_read = Path.read_bytes
        def read(path):
            if path.name == ".env":
                raise AssertionError("secret was read")
            return real_read(path)
        with mock.patch.object(Path, "read_bytes", read):
            manifest = self.init()
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(manifest["files"][".env"]["status"], "excluded")
        self.assertNotIn("before", manifest["files"][".env"])
        self.assertIn(".claude/custom.md", manifest["files"])
        self.assertIn("sub/AGENTS.md", manifest["files"])
        self.assertFalse((self.root / ".agent-runtime").exists())

    def test_unread_or_unresolved_plan_cannot_be_sealed(self):
        manifest = self.init()
        TOOL.draft(self.session, manifest, self.root, self.source)
        with self.assertRaisesRegex(ValueError, "unresolved"):
            TOOL.seal(self.session, manifest, self.root, "answer")
        plan = TOOL.load(self.session / "plan.json")
        plan.update(unresolved=[], acceptance=["check"])
        TOOL.save(self.session / "plan.json", plan)
        with self.assertRaisesRegex(ValueError, "full read"):
            TOOL.seal(self.session, manifest, self.root, "answer")

    def test_read_attestation_requires_exact_revision(self):
        manifest = self.init()
        with self.assertRaisesRegex(ValueError, "revision"):
            TOOL.coverage(self.session, manifest, self.root, "AGENTS.md", "cover", "wrong")
        before = manifest["files"]["AGENTS.md"]["before"]["sha256"]
        (self.root / "AGENTS.md").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "revision"):
            TOOL.coverage(self.session, manifest, self.root, "AGENTS.md", "cover", before)

    def test_promoted_reference_is_covered_and_its_drift_blocks(self):
        (self.root / "workflow-helper.txt").write_text("workflow command\n")
        manifest = self.init()
        TOOL.coverage(self.session, manifest, self.root, "workflow-helper.txt", "include", "")
        for name, item in manifest["files"].items():
            if item["status"] == "unread":
                TOOL.coverage(self.session, manifest, self.root, name, "cover", item["before"]["sha256"])
        TOOL.draft(self.session, manifest, self.root, self.source)
        plan = TOOL.load(self.session / "plan.json")
        plan.update(unresolved=[], acceptance=["pass"])
        plan["dispositions"] = [{"path": name, "action": "replace" if name == "AGENTS.md" else "keep", "reason": "mapped"}
                                for name, item in manifest["files"].items() if item["status"] == "read"]
        TOOL.save(self.session / "plan.json", plan)
        self.seal_ready(manifest, "accepted")
        (self.root / "workflow-helper.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "revision changed"):
            TOOL.check_target(manifest, plan, self.root)

    def test_roundtrip_dirty_bytes_permissions_and_untracked_work(self):
        before = (self.root / "AGENTS.md").read_bytes()
        manifest, plan, receipt = self.prepare()
        result = self.apply(manifest, receipt)
        self.assertEqual(result["status"], "APPLIED")
        self.assertIn("Preserve business rules", (self.root / "AGENTS.md").read_text())
        self.assertNotIn("Source project-only", (self.root / "AGENTS.md").read_text())
        self.assertFalse((self.root / ".lean/PROJECT.md").exists())
        self.assertFalse((self.root / ".lean/config.json").exists())
        self.assertFalse((self.root / ".claude/settings.json").exists())
        self.assertEqual((self.root / ".env").read_text(), "DO_NOT_READ_OR_COPY\n")
        self.assertEqual((self.root / "application.txt").read_text(), "unrelated pending work\n")
        TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), before)
        self.assertEqual((self.root / "AGENTS.md").stat().st_mode & 0o777, 0o640)
        self.assertFalse((self.root / "new").exists())
        self.assertFalse((self.root / ".lean").exists())

    def test_reapply_verifies_without_rewriting(self):
        manifest, _, receipt = self.prepare()
        self.apply(manifest, receipt)
        before = (self.root / "AGENTS.md").stat().st_mtime_ns
        with mock.patch.object(TOOL, "atomic", wraps=TOOL.atomic) as writer:
            self.apply(manifest, receipt)
        self.assertEqual((self.root / "AGENTS.md").stat().st_mtime_ns, before)
        self.assertTrue(all(self.root not in call.args[0].parents for call in writer.call_args_list))

    def test_stale_target_source_plan_and_new_workflow_file_block(self):
        manifest, plan, receipt = self.prepare()
        for kind in ("target", "source", "plan", "new-file"):
            with self.subTest(kind=kind):
                if kind == "target":
                    path = self.root / "AGENTS.md"
                elif kind == "source":
                    path = self.source / ".lean/LICENSE"
                elif kind == "plan":
                    path = self.session / "plan.json"
                else:
                    path = self.root / "new-rules.md"
                before = path.read_bytes() if path.exists() else None
                path.write_text(path.read_text() + " " if before is not None and kind != "plan" else "new rules")
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    self.apply(manifest, receipt)
                self.assertFalse((self.session / "journal.json").exists())
                if before is None:
                    path.unlink()
                else:
                    path.write_bytes(before)
        changed = copy.deepcopy(plan)
        changed["operations"][0]["content"] += "Changed after approval"
        TOOL.save(self.session / "plan.json", changed)
        with self.assertRaisesRegex(ValueError, "approved plan"):
            self.apply(manifest, receipt)

    def test_symlink_paths_and_session_inside_target_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            TOOL.initial(self.root, self.root / "session")
        external = self.base / "external"
        external.mkdir()
        (self.root / "link").symlink_to(external, target_is_directory=True)
        manifest = self.init()
        self.assertEqual(manifest["files"]["link"]["status"], "excluded")
        with self.assertRaisesRegex(ValueError, "symlink"):
            TOOL.target_path(self.root, "link/rules.md")
        with self.assertRaisesRegex(ValueError, "protected"):
            TOOL.coverage(self.session, manifest, self.root, ".env", "include", "")

    def test_traversal_duplicate_paths_and_keep_contradiction_block(self):
        manifest, plan, _ = self.prepare()
        for name in ("../outside", "/absolute", ".git/config", ".env", "a/../b", "a\\b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                TOOL.target_path(self.root, name)
        changed = copy.deepcopy(plan)
        changed["operations"].append(changed["operations"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            TOOL.validate_plan(manifest, changed)
        changed = copy.deepcopy(plan)
        changed["dispositions"][0]["action"] = "keep"
        with self.assertRaisesRegex(ValueError, "contradicts"):
            TOOL.validate_plan(manifest, changed)

    def test_active_claims_block_without_releasing_or_exposing_tokens(self):
        manifest, _, receipt = self.prepare()
        claims = self.root / ".agent-runtime/claims"
        claims.mkdir(parents=True)
        path = claims / "Q0001.json"
        path.write_text(json.dumps({"expires_at": time.time() + 3600, "token": "PRIVATE_RECEIPT"}))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "active workflow claims"):
            self.apply(manifest, receipt)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.session / "journal.json").exists())

    def test_crash_after_write_before_receipt_resumes(self):
        manifest, _, receipt = self.prepare()
        real_save = TOOL.save
        crashed = False
        def save(path, value):
            nonlocal crashed
            if path.name == "journal.json" and value["completed"] and not crashed:
                crashed = True
                raise RuntimeError("simulated power loss after file write")
            return real_save(path, value)
        with mock.patch.object(TOOL, "save", save), self.assertRaisesRegex(RuntimeError, "power loss"):
            self.apply(manifest, receipt)
        journal = TOOL.load(self.session / "journal.json")
        self.assertEqual(len(journal["started"]), 1)
        self.assertEqual(journal["completed"], [])
        self.assertEqual(self.apply(manifest, receipt)["status"], "APPLIED")
        TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Dirty original: preserve business rules\n")

    def test_rollback_preflight_keeps_all_files_when_subsequent_edit_exists(self):
        manifest, _, receipt = self.prepare()
        self.apply(manifest, receipt)
        (self.root / "new/deep.txt").write_text("subsequent user work\n")
        before = (self.root / "AGENTS.md").read_bytes()
        with self.assertRaisesRegex(ValueError, "subsequent edits"):
            TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), before)
        self.assertEqual((self.root / "new/deep.txt").read_text(), "subsequent user work\n")

    def test_rollback_without_baseline_and_interrupted_restore(self):
        manifest, _, receipt = self.prepare()
        self.apply(manifest, receipt)
        self.source.rename(self.base / "removed source")
        real_save = TOOL.save
        def save(path, value):
            if path.name == "journal.json" and value["state"] == "ROLLING_BACK" and value["restored"]:
                raise RuntimeError("simulated crash during restoration")
            return real_save(path, value)
        with mock.patch.object(TOOL, "save", save), self.assertRaises(RuntimeError):
            TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual(TOOL.rollback(self.session, manifest, self.root)["status"], "ROLLED_BACK")
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Dirty original: preserve business rules\n")

    def test_delete_is_recoverable_and_unread_original_cannot_be_deleted(self):
        (self.root / "old-rules.md").write_text("legacy rules\n")
        manifest, plan, _ = self.prepare()
        (self.session / "approval.json").unlink()
        plan["operations"].append({"path": "old-rules.md", "before": manifest["files"]["old-rules.md"]["before"],
                                   "content": None, "reason": "retire competing entrypoint"})
        for item in plan["dispositions"]:
            if item["path"] == "old-rules.md":
                item["action"] = "retire"
        TOOL.save(self.session / "plan.json", plan)
        receipt = self.seal_ready(manifest, "accepted retirement")
        self.apply(manifest, receipt)
        self.assertFalse((self.root / "old-rules.md").exists())
        self.apply(manifest, receipt)
        TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual((self.root / "old-rules.md").read_text(), "legacy rules\n")

    def test_existing_lean_records_are_preserved_by_writer(self):
        (self.root / "docs/tracking").mkdir(parents=True)
        (self.root / "docs/tracking/TCK001.md").write_text("Status: PLANNED\n")
        manifest, plan, _ = self.prepare()
        path = "docs/tracking/TCK001.md"
        for item in plan["dispositions"]:
            if item["path"] == path:
                item["action"] = "migrate"
        plan["operations"].append({"path": path, "before": manifest["files"][path]["before"],
                                   "content": "Status: DONE\n", "mode": 0o644, "reason": "bad migration"})
        with self.assertRaisesRegex(ValueError, "records must remain"):
            TOOL.validate_plan(manifest, plan)

    def foreign_queue_plan(self, status="DONE"):
        name = ".agents/queue/items/Q0001.json"
        original = {"id": "Q0001", "workset": "TCK001", "task": "TASK-001",
                    "title": "Foreign task", "status": status, "dependencies": [],
                    "exclusiveScopes": ["file:app.py"], "objective": "Keep decisions",
                    "completion": {"evidence": ["Original test: PASS"]}}
        path = self.root / name
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(original) + "\n")
        manifest, plan, _ = self.prepare()
        (self.session / "approval.json").unlink()  # Extend the fixture before its final approval.
        archive = (".agents/queue/retired/Q0001.txt" if status == "CANCELLED"
                   else "docs/history/agent-workflow/Q0001.txt")
        output = None if status == "CANCELLED" else {
            "id": "Q0001", "tracker": "TCK001", "title": original["title"],
            "status": status, "dependencies": [], "scopes": original["exclusiveScopes"],
            "evidence": "Original test: PASS" if status == "DONE" else None, "legacy": original}
        plan["operations"] += [
            {"path": archive, "before": None, "content": path.read_text(),
             "mode": 0o644, "reason": "retain exact original"},
            {"path": name, "before": manifest["files"][name]["before"],
             "content": json.dumps(output) if output else None,
             "mode": 0o644, "reason": "explicit foreign conversion"}]
        for disposition in plan["dispositions"]:
            if disposition["path"] == name:
                disposition["action"] = "migrate"
        support = {".gitignore": ".agent-runtime/\n",
                   "docs/tracking/TEMPLATE.md": "Template\n",
                   "docs/tracking/README.md": "Guide\n",
                   ".agents/queue/README.md": "Guide\n"}
        if status != "CANCELLED":
            support["docs/tracking/TCK001.md"] = "Status: " + status + "\n\n## Evidence\n- Original test: PASS\n"
        for support_path, content in support.items():
            plan["operations"].append({"path": support_path, "before": None,
                "content": content, "mode": 0o644, "reason": "fixture record support"})
        plan["record_migrations"] = [{"source": name, "archive": archive,
            "format": "casetodian-v1", "kind": "queue", "decision": "D1"}]
        return manifest, plan, original

    def test_foreign_queue_conversion_retains_original_and_recovers(self):
        manifest, plan, original = self.foreign_queue_plan()
        TOOL.save(self.session / "plan.json", plan)
        receipt = self.seal_ready(manifest, "fixture accepts explicit foreign mapping")
        self.apply(manifest, receipt)
        self.assertEqual(TOOL.load(self.root / ".agents/queue/items/Q0001.json")["legacy"], original)
        TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual(TOOL.load(self.root / ".agents/queue/items/Q0001.json"), original)
        self.assertFalse((self.root / "docs/history/agent-workflow/Q0001.txt").exists())

    def test_foreign_mapping_rejects_loss_and_missing_decision(self):
        manifest, plan, _ = self.foreign_queue_plan()
        with self.subTest("archive bytes"):
            bad = copy.deepcopy(plan)
            next(op for op in bad["operations"] if op["path"] == bad["record_migrations"][0]["archive"])["content"] += "changed"
            with self.assertRaisesRegex(ValueError, "exact original"):
                TOOL.validate_plan(manifest, bad)
        with self.subTest("evidence"):
            bad = copy.deepcopy(plan)
            operation = next(op for op in bad["operations"] if op["path"] == bad["record_migrations"][0]["source"])
            data = json.loads(operation["content"])
            data["evidence"] = "invented pass"
            operation["content"] = json.dumps(data)
            with self.assertRaisesRegex(ValueError, "queue mapping"):
                TOOL.validate_plan(manifest, bad)
        with self.subTest("decision"):
            bad = copy.deepcopy(plan)
            bad["record_migrations"][0]["decision"] = "not-approved"
            with self.assertRaisesRegex(ValueError, "decision"):
                TOOL.validate_plan(manifest, bad)

    def test_cancelled_record_is_only_retired_never_completed(self):
        manifest, plan, _ = self.foreign_queue_plan("CANCELLED")
        TOOL.validate_plan(manifest, plan)
        bad = copy.deepcopy(plan)
        next(op for op in bad["operations"] if op["path"] == bad["record_migrations"][0]["source"])["content"] = "{}"
        with self.assertRaisesRegex(ValueError, "CANCELLED"):
            TOOL.validate_plan(manifest, bad)

    def test_foreign_blocked_record_cannot_be_marked_done(self):
        manifest, plan, _ = self.foreign_queue_plan("BLOCKED")
        TOOL.validate_plan(manifest, plan)
        op = next(op for op in plan["operations"] if op["path"] == plan["record_migrations"][0]["source"])
        data = json.loads(op["content"])
        data["status"] = "DONE"
        op["content"] = json.dumps(data)
        with self.assertRaisesRegex(ValueError, "queue mapping"):
            TOOL.validate_plan(manifest, plan)

    def test_foreign_mapping_does_not_accept_existing_lean_queue(self):
        manifest, plan, old = self.foreign_queue_plan()
        archive = next(op for op in plan["operations"] if op["path"] == plan["record_migrations"][0]["archive"])
        old["tracker"] = "TCK001"
        archive["content"] = json.dumps(old)
        manifest["files"][plan["record_migrations"][0]["source"]]["before"]["sha256"] = TOOL.digest(archive["content"].encode())
        with self.assertRaisesRegex(ValueError, "existing Lean records must remain"):
            TOOL.record_migration_sources(manifest, plan)

    def test_foreign_stage_validation_rejects_missing_tracker(self):
        manifest, plan, _ = self.foreign_queue_plan()
        plan["operations"] = [op for op in plan["operations"] if op["path"] != "docs/tracking/TCK001.md"]
        TOOL.save(self.session / "plan.json", plan)
        TOOL.stage(self.session, manifest, self.root)
        with self.assertRaisesRegex(ValueError, "expected one tracker"):
            TOOL.stage_check(self.session, manifest, self.root, "claimed passing validation")
        self.assertFalse((self.session / "approval.json").exists())

    def test_foreign_conversion_resume_after_archive_write(self):
        manifest, plan, original = self.foreign_queue_plan()
        TOOL.save(self.session / "plan.json", plan)
        receipt = self.seal_ready(manifest, "fixture approval")
        real_atomic = TOOL.atomic
        source = self.root / plan["record_migrations"][0]["source"]
        def crash(path, data, mode=0o600):
            if path == source:
                raise OSError("interrupted conversion")
            return real_atomic(path, data, mode)
        with mock.patch.object(TOOL, "atomic", crash):
            with self.assertRaisesRegex(OSError, "interrupted conversion"):
                self.apply(manifest, receipt)
        self.assertEqual(TOOL.load(source), original)
        self.assertTrue((self.root / plan["record_migrations"][0]["archive"]).exists())
        self.apply(manifest, receipt)
        TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual(TOOL.load(source), original)

    def test_foreign_tracker_requires_unambiguous_status_and_original_route(self):
        manifest, plan, _ = self.foreign_queue_plan()
        source = "docs/tracking/TCK001.md"
        original = "# Legacy\nStatus: REVIEW\n## Tasks and queue mapping\n- [x] TASK-001 | Q0001 | DONE\n"
        archive = "docs/history/agent-workflow/TCK001.txt"
        manifest["files"][source] = {"status": "read", "before": {"sha256": TOOL.digest(original.encode()), "mode": 0o644}}
        plan["dispositions"].append({"path": source, "action": "migrate", "reason": "explicit tracker migration"})
        plan["operations"] = [op for op in plan["operations"] if op["path"] != source]
        plan["operations"] += [
            {"path": archive, "before": None, "content": original, "mode": 0o644, "reason": "exact original"},
            {"path": source, "before": manifest["files"][source]["before"],
             "content": "Status: REVIEWING\nOriginal: " + archive + "\n", "mode": 0o644, "reason": "retain review state"}]
        plan["record_migrations"].append({"source": source, "archive": archive,
            "format": "casetodian-v1", "kind": "tracker", "decision": "D1", "status": "REVIEWING"})
        TOOL.validate_plan(manifest, plan)
        bad = copy.deepcopy(plan)
        bad["record_migrations"][-1]["status"] = "DONE"
        with self.assertRaisesRegex(ValueError, "status is ambiguous"):
            TOOL.validate_plan(manifest, bad)
        bad = copy.deepcopy(plan)
        bad["operations"][-1]["content"] = "Status: REVIEWING\n"
        with self.assertRaisesRegex(ValueError, "route to its original"):
            TOOL.validate_plan(manifest, bad)

    def test_done_tracker_cannot_invent_completion_evidence(self):
        manifest, plan, _ = self.foreign_queue_plan()
        source = "docs/tracking/TCK001.md"
        original = "# Legacy\nStatus: DONE\n## Tasks and queue mapping\n- [x] TASK-001 | Q0001 | DONE\n"
        (self.root / source).parent.mkdir(parents=True, exist_ok=True)
        (self.root / source).write_text(original)
        TOOL.coverage(self.session, manifest, self.root, source, "include", "")
        TOOL.coverage(self.session, manifest, self.root, source, "cover", manifest["files"][source]["before"]["sha256"])
        archive = "docs/history/agent-workflow/TCK001.txt"
        plan["dispositions"].append({"path": source, "action": "migrate", "reason": "explicit tracker migration"})
        plan["operations"] = [op for op in plan["operations"] if op["path"] != source]
        plan["operations"] += [
            {"path": archive, "before": None, "content": original, "mode": 0o644, "reason": "original"},
            {"path": source, "before": manifest["files"][source]["before"],
             "content": "Status: DONE\nOriginal: " + archive + "\n## Evidence\n- fabricated test: PASS\n",
             "mode": 0o644, "reason": "bad invented evidence"}]
        plan["record_migrations"].append({"source": source, "archive": archive,
            "format": "casetodian-v1", "kind": "tracker", "decision": "D1", "status": "DONE",
            "evidence": ["fabricated test: PASS"]})
        TOOL.save(self.session / "plan.json", plan)
        with self.assertRaisesRegex(ValueError, "original tracker evidence"):
            TOOL.stage(self.session, manifest, self.root)
        self.assertEqual((self.root / source).read_text(), original)
        self.assertFalse((self.session / "approval.json").exists())
        original += "## Validation evidence\nOriginal test: PASS\n"
        (self.root / source).write_text(original)
        TOOL.coverage(self.session, manifest, self.root, source, "include", "")
        TOOL.coverage(self.session, manifest, self.root, source, "cover", manifest["files"][source]["before"]["sha256"])
        plan["operations"][-2]["content"] = original
        plan["operations"][-1]["before"] = manifest["files"][source]["before"]
        plan["operations"][-1]["content"] = "Status: DONE\nOriginal: " + archive + "\n## Evidence\n- Original test: PASS\n"
        plan["record_migrations"][-1]["evidence"] = ["Original test: PASS"]
        TOOL.save(self.session / "plan.json", plan)
        TOOL.stage(self.session, manifest, self.root)
        TOOL.stage_check(self.session, manifest, self.root, "source-bound completion evidence and records validated")
        plan["operations"][-1]["content"] += "- fabricated extra proof\n"
        with self.assertRaisesRegex(ValueError, "only selected original tracker evidence"):
            TOOL.validate_plan(manifest, plan)

    def test_foreign_tasks_heading_variant_retains_existing_lean_guard(self):
        manifest, plan, _ = self.foreign_queue_plan()
        source = "docs/tracking/TCK001.md"
        archive = "docs/history/agent-workflow/TCK001.txt"
        original = "# TCK001 - Legacy\nStatus: REVIEW (pending live check)\n## Tasks\n[x] TASK-001 | Q0001 | DONE\n"
        manifest["files"][source] = {"status": "read", "before": {"sha256": TOOL.digest(original.encode()), "mode": 0o644}}
        plan["dispositions"].append({"path": source, "action": "migrate", "reason": "foreign heading variant"})
        plan["operations"] = [op for op in plan["operations"] if op["path"] != source]
        plan["operations"] += [
            {"path": archive, "before": None, "content": original, "mode": 0o644, "reason": "exact original"},
            {"path": source, "before": manifest["files"][source]["before"],
             "content": "Status: REVIEWING\nOriginal: " + archive + "\n", "mode": 0o644, "reason": "review state retained"}]
        plan["record_migrations"].append({"source": source, "archive": archive,
            "format": "casetodian-v1", "kind": "tracker", "decision": "D1", "status": "REVIEWING"})
        TOOL.validate_plan(manifest, plan)
        conflict = original + "Status: IN_PROGRESS\n"
        plan["operations"][-2]["content"] = conflict
        manifest["files"][source]["before"]["sha256"] = TOOL.digest(conflict.encode())
        with self.assertRaisesRegex(ValueError, "status is ambiguous"):
            TOOL.validate_plan(manifest, plan)
        plan["decisions"].append({"id": "explicit-state", "choice": "Use REVIEWING, preserve historical statements",
            "evidence": "fixture human decision", "record_statuses": {source: "REVIEWING"}})
        plan["record_migrations"][-1]["status_decision"] = "explicit-state"
        TOOL.validate_plan(manifest, plan)
        native = "# TCK001\nStatus: REVIEWING\n## Tasks\n- [ ] TASK-01: Open\n## Evidence\n"
        for content in (native, native.replace("\n", "\r\n"), native.replace("Status: REVIEWING\n", "Status: REVIEWING\r\n").replace("## Evidence\n", "## Evidence\r\n")):
            plan["operations"][-2]["content"] = content
            manifest["files"][source]["before"]["sha256"] = TOOL.digest(content.encode())
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "existing Lean records must remain"):
                TOOL.validate_plan(manifest, plan)

    def test_parent_tracker_evidence_needs_explicit_read_source_resolution(self):
        manifest, plan, _ = self.foreign_queue_plan()
        child, parent = "docs/tracking/TCK001.md", "docs/tracking/TCK002.md"
        proof = "Published tests PASS; visual acceptance waived"
        plan["operations"] = [op for op in plan["operations"] if op["path"] != child]
        for source, state, extra in ((child, "REVIEW", ""), (parent, "DONE", "## Validation and acceptance\n" + proof + "\n")):
            original = "# Legacy\nInline Status: " + state + "\n## Tasks\n- historical task\n" + extra
            archive = "docs/history/agent-workflow/" + Path(source).stem + ".txt"
            before = {"sha256": TOOL.digest(original.encode()), "mode": 0o644}
            manifest["files"][source] = {"status": "read", "before": before}
            plan["dispositions"].append({"path": source, "action": "migrate", "reason": "source-bound historical resolution"})
            plan["operations"] += [
                {"path": archive, "before": None, "content": original, "mode": 0o644, "reason": "exact original"},
                {"path": source, "before": before, "content": "Status: DONE\nOriginal: " + archive + "\n## Evidence\n- " + proof + "\n",
                 "mode": 0o644, "reason": "resolved state with retained waiver"}]
            plan["record_migrations"].append({"source": source, "archive": archive,
                "format": "casetodian-v1", "kind": "tracker", "decision": "D1", "status": "DONE", "evidence": [proof]})
        plan["decisions"].append({"id": "published-resolution", "choice": "Use later publication, keep waiver",
            "evidence": "fixture user answer", "record_statuses": {child: "DONE"}, "record_evidence_sources": {child: parent}})
        mapping = plan["record_migrations"][-2]
        mapping.update(status_decision="published-resolution", evidence_source=parent)
        TOOL.validate_plan(manifest, plan)
        for mutation in ("missing-decision", "unread", "changed-proof", "unsourced-extra"):
            bad, inventory = copy.deepcopy(plan), copy.deepcopy(manifest)
            if mutation == "missing-decision":
                bad["decisions"][-1].pop("record_evidence_sources")
            elif mutation == "unread":
                inventory["files"][parent]["status"] = "unread"
            elif mutation == "changed-proof":
                next(op for op in bad["operations"] if op["path"] == bad["record_migrations"][-1]["archive"])["content"] += "extra\n"
            else:
                bad["record_migrations"][-2]["evidence"] = ["visual acceptance PASS"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                TOOL.validate_plan(inventory, bad)

    def test_foreign_snapshot_and_handoff_evidence_headings(self):
        manifest, plan, source, archive, original = self.history_tracker_plan()
        mapping = plan["record_migrations"][-1]
        mapping.pop("historical_only")
        mapping.pop("history_decision")
        proof = "Backup rehearsal PASS; no live browser run."
        plan["operations"][-1]["content"] = "Status: DONE\nOriginal: " + archive + "\n## Evidence\n- " + proof + "\n"
        for heading in ("Execution snapshot", "Impact and validation", "Validation and handoff"):
            content = original.replace("## Validation evidence", "## " + heading)
            plan["operations"][-2]["content"] = content
            manifest["files"][source]["before"]["sha256"] = TOOL.digest(content.encode())
            mapping["evidence"] = [proof]
            with self.subTest(heading=heading):
                TOOL.validate_plan(manifest, plan)
                mapping["evidence"] = ["Live browser PASS"]
                with self.assertRaisesRegex(ValueError, "original tracker evidence"):
                    TOOL.validate_plan(manifest, plan)

    def history_tracker_plan(self):
        manifest, plan, _ = self.foreign_queue_plan()
        source = "docs/tracking/TCK002.md"
        archive = "docs/history/agent-workflow/TCK002.txt"
        original = "# Historical DB-only work\nInline Status: DONE\n## Tasks\nNo queue: user-approved local DB operation; no repository-file scope.\n## Validation evidence\nBackup rehearsal PASS; no live browser run.\n"
        (self.root / source).parent.mkdir(parents=True, exist_ok=True)
        (self.root / source).write_text(original)
        TOOL.coverage(self.session, manifest, self.root, source, "include", "")
        TOOL.coverage(self.session, manifest, self.root, source, "cover", manifest["files"][source]["before"]["sha256"])
        plan["decisions"].append({"id": "closed-history", "choice": "Keep closed no-queue work as history",
            "evidence": "fixture explicit user choice", "archived_trackers": [source]})
        plan["dispositions"].append({"path": source, "action": "retire", "reason": "closed no-queue work; no invented queue ID"})
        plan["operations"] += [
            {"path": archive, "before": None, "content": original, "mode": 0o644, "reason": "exact inert original"},
            {"path": source, "before": manifest["files"][source]["before"], "content": None, "mode": 0o644,
             "reason": "closed work retained in history"}]
        plan["record_migrations"].append({"source": source, "archive": archive, "format": "casetodian-v1",
            "kind": "tracker", "decision": "D1", "status": "DONE", "historical_only": True,
            "history_decision": "closed-history"})
        return manifest, plan, source, archive, original

    def test_closed_foreign_tracker_history_is_lossless_and_recoverable(self):
        manifest, plan, source, archive, original = self.history_tracker_plan()
        TOOL.save(self.session / "plan.json", plan)
        receipt = self.seal_ready(manifest, "fixture accepted exact closed tracker history")
        self.apply(manifest, receipt)
        self.assertFalse((self.root / source).exists())
        self.assertEqual((self.root / archive).read_text(), original)
        TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual((self.root / source).read_text(), original)
        self.assertFalse((self.root / archive).exists())

    def test_history_tracker_needs_closed_state_and_exact_user_decision(self):
        manifest, plan, source, archive, original = self.history_tracker_plan()
        TOOL.validate_plan(manifest, plan)
        for mutation in ("no-decision", "wrong-source", "open-state", "retained-active", "native"):
            bad, inventory = copy.deepcopy(plan), copy.deepcopy(manifest)
            if mutation == "no-decision":
                bad["record_migrations"][-1].pop("history_decision")
            elif mutation == "wrong-source":
                bad["decisions"][-1]["archived_trackers"] = ["docs/tracking/TCK003.md"]
            elif mutation == "open-state":
                content = original.replace("DONE", "REVIEW")
                bad["operations"][-2]["content"] = content
                inventory["files"][source]["before"]["sha256"] = TOOL.digest(content.encode())
                bad["record_migrations"][-1]["status"] = "REVIEWING"
            elif mutation == "retained-active":
                bad["operations"][-1]["content"] = "Status: DONE\n"
            else:
                content = "Status: DONE\n## Tasks\n## Evidence\n- PASS\n"
                bad["operations"][-2]["content"] = content
                inventory["files"][source]["before"]["sha256"] = TOOL.digest(content.encode())
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                TOOL.validate_plan(inventory, bad)

    def test_history_tracker_cannot_leave_linked_queue_without_tracker(self):
        manifest, plan, source, archive, original = self.history_tracker_plan()
        queue = next(op for op in plan["operations"] if op["path"] == ".agents/queue/items/Q0001.json")
        item = json.loads(queue["content"])
        item["tracker"] = item["legacy"]["workset"] = "TCK002"
        queue["content"] = json.dumps(item)
        saved = next(op for op in plan["operations"] if op["path"] == plan["record_migrations"][0]["archive"])
        saved["content"] = json.dumps(item["legacy"])
        (self.root / queue["path"]).write_text(saved["content"])
        TOOL.coverage(self.session, manifest, self.root, queue["path"], "include", "")
        TOOL.coverage(self.session, manifest, self.root, queue["path"], "cover", manifest["files"][queue["path"]]["before"]["sha256"])
        queue["before"] = manifest["files"][queue["path"]]["before"]
        TOOL.save(self.session / "plan.json", plan)
        TOOL.stage(self.session, manifest, self.root)
        with self.assertRaises(ValueError):
            TOOL.stage_check(self.session, manifest, self.root, "cannot archive a linked tracker")

    def evidence_history_plan(self, named=True):
        manifest, plan, parent, _, _ = self.history_tracker_plan()
        filename = "TCK002-review.md" if named else "model-benchmark.md"
        source = "docs/tracking/evidence/" + filename
        archive = "docs/history/agent-workflow/evidence/" + filename + ".txt"
        original = "# TCK002 old review\nReviewer: .claude/agents/lead-reviewer.md\nPASS with live browser NOT_RUN.\n"
        if not named:
            original += "Referenced by: `" + parent + "`.\n"
        (self.root / source).parent.mkdir(parents=True, exist_ok=True)
        (self.root / source).write_text(original)
        TOOL.coverage(self.session, manifest, self.root, source, "include", "")
        TOOL.coverage(self.session, manifest, self.root, source, "cover", manifest["files"][source]["before"]["sha256"])
        plan["dispositions"].append({"path": source, "action": "retire", "reason": "exact foreign workset evidence history"})
        plan["operations"] += [
            {"path": archive, "before": None, "content": original, "mode": 0o644, "reason": "exact inert evidence original"},
            {"path": source, "before": manifest["files"][source]["before"], "content": None, "mode": 0o644,
             "reason": "retain foreign review as history"}]
        plan["record_migrations"].append({"source": source, "archive": archive, "format": "casetodian-v1",
            "kind": "evidence-history", "decision": "D1", "parent": parent})
        return manifest, plan, source, archive, original

    def test_foreign_workset_evidence_history_is_exact_and_recoverable(self):
        manifest, plan, source, archive, original = self.evidence_history_plan()
        TOOL.save(self.session / "plan.json", plan)
        receipt = self.seal_ready(manifest, "fixture accepts foreign tracker and related evidence history")
        self.apply(manifest, receipt)
        self.assertFalse((self.root / source).exists())
        self.assertEqual((self.root / archive).read_text(), original)
        TOOL.rollback(self.session, manifest, self.root)
        self.assertEqual((self.root / source).read_text(), original)
        self.assertFalse((self.root / archive).exists())

    def test_evidence_history_cannot_opt_out_native_or_unrelated_records(self):
        manifest, plan, source, archive, original = self.evidence_history_plan()
        TOOL.validate_plan(manifest, plan)
        for mutation in ("missing-parent", "wrong-workset", "rewrite-proof", "native-parent"):
            bad, inventory = copy.deepcopy(plan), copy.deepcopy(manifest)
            if mutation == "missing-parent":
                bad["record_migrations"][-1]["parent"] = "docs/tracking/TCK999.md"
            elif mutation == "wrong-workset":
                bad["record_migrations"][-1]["parent"] = "docs/tracking/TCK001.md"
            elif mutation == "rewrite-proof":
                bad["operations"][-1]["content"] = "PASS all live checks\n"
            else:
                parent = bad["record_migrations"][-2]
                content = "Status: DONE\n## Tasks\n## Evidence\n- PASS\n"
                next(op for op in bad["operations"] if op["path"] == parent["archive"])["content"] = content
                inventory["files"][parent["source"]]["before"]["sha256"] = TOOL.digest(content.encode())
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                TOOL.validate_plan(inventory, bad)

    def test_unnamed_evidence_needs_explicit_original_parent_reference(self):
        manifest, plan, source, archive, original = self.evidence_history_plan(named=False)
        TOOL.validate_plan(manifest, plan)
        content = original.split("Referenced by:", 1)[0]
        plan["operations"][-2]["content"] = content
        manifest["files"][source]["before"]["sha256"] = TOOL.digest(content.encode())
        with self.assertRaisesRegex(ValueError, "mapped foreign tracker"):
            TOOL.validate_plan(manifest, plan)

    def test_record_guides_can_be_reconciled_without_record_override(self):
        name = "docs/tracking/README.md"
        path = self.root / name
        path.parent.mkdir(parents=True)
        path.write_text("Old workflow instructions\n")
        manifest, plan, _ = self.prepare()
        for disposition in plan["dispositions"]:
            if disposition["path"] == name:
                disposition["action"] = "replace"
        plan["operations"].append({"path": name, "before": manifest["files"][name]["before"],
            "content": "Lean workflow guide\n", "mode": 0o644, "reason": "reconcile workflow support guide"})
        TOOL.validate_plan(manifest, plan)

    def test_snapshot_corruption_and_wrong_receipt_block_recovery(self):
        manifest, _, receipt = self.prepare()
        with self.assertRaisesRegex(ValueError, "sealed plan hash"):
            TOOL.apply_plan(self.session, manifest, self.root, "wrong")
        self.apply(manifest, receipt)
        journal = TOOL.load(self.session / "journal.json")
        for item in journal["snapshots"]:
            if item["before"] is not None:
                item["data"] = "Y29ycnVwdA=="
        TOOL.save(self.session / "journal.json", journal)
        with self.assertRaisesRegex(ValueError, "checksum"):
            TOOL.rollback(self.session, manifest, self.root)

    def test_cli_status_is_compact_and_does_not_print_snapshots(self):
        manifest, _, receipt = self.prepare()
        self.cli("apply", "--session", str(self.session), "--approval", receipt["plan_sha256"])
        result = self.cli("status", "--session", str(self.session))
        self.assertEqual(json.loads(result.stdout)["state"], "APPLIED")
        self.assertNotIn("snapshots", result.stdout)
        self.assertNotIn("Dirty original", result.stdout)
        self.cli("rollback", "--session", str(self.session))
        self.cli("resume", "--session", str(self.session), "--approval", receipt["plan_sha256"], success=False)

    def test_explicit_os_alias_root_is_canonicalized(self):
        alias = Path(self.temporary.name) / "dirty target"
        result = self.cli("inventory", str(alias), "--session", str(self.session))
        self.assertEqual(json.loads(result.stdout)["inventory"]["target"], str(self.root))

    def test_nested_repository_cannot_be_promoted_or_written(self):
        nested = self.root / "vendor/repo"
        nested.mkdir(parents=True)
        (nested / ".git").write_text("gitdir: external\n")
        (nested / "AGENTS.md").write_text("another repository's rules\n")
        manifest = self.init()
        self.assertEqual(manifest["files"]["vendor/repo"]["status"], "excluded")
        with self.assertRaisesRegex(ValueError, "nested repository"):
            TOOL.coverage(self.session, manifest, self.root, "vendor/repo/AGENTS.md", "include", "")
        with self.assertRaisesRegex(ValueError, "nested repository"):
            TOOL.target_path(self.root, "vendor/repo/new.md")

    def test_draft_does_not_import_source_project_capabilities(self):
        (self.source / ".claude/skills/application-helper").mkdir()
        (self.source / ".claude/skills/application-helper/SKILL.md").write_text("Deploy source application\n")
        (self.source / ".claude/agents/deployer.md").write_text("Source application agent\n")
        manifest = self.init()
        TOOL.draft(self.session, manifest, self.root, self.source)
        plan = TOOL.load(self.session / "plan.json")
        names = {op["path"] for op in plan["operations"]}
        self.assertNotIn(".claude/skills/application-helper/SKILL.md", names)
        self.assertNotIn(".claude/agents/deployer.md", names)

    def test_draft_does_not_import_unregistered_source_script_or_template(self):
        (self.source / ".lean/scripts/deploy-client.py").write_text("SOURCE_PROJECT_APPLICATION_FACTS = True\n")
        (self.source / ".lean/templates/customer-note.md").write_text("Source customer data\n")
        manifest = self.init()
        TOOL.draft(self.session, manifest, self.root, self.source)
        names = {op["path"] for op in TOOL.load(self.session / "plan.json")["operations"]}
        self.assertNotIn(".lean/scripts/deploy-client.py", names)
        self.assertNotIn(".lean/templates/customer-note.md", names)

    def test_operator_excluded_product_doc_is_preserved_and_drift_blocks(self):
        (self.root / "product.md").write_text("Unrelated product prose\n")
        manifest, plan, _ = self.prepare()
        (self.session / "approval.json").unlink()
        TOOL.coverage(self.session, manifest, self.root, "product.md", "exclude", "Product prose; no workflow references")
        receipt = self.seal_ready(manifest, "fixture accepted exclusion and diff")
        self.apply(manifest, receipt)
        self.assertEqual((self.root / "product.md").read_text(), "Unrelated product prose\n")
        (self.root / "product.md").write_text("Changed after audit\n")
        with self.assertRaisesRegex(ValueError, "excluded file changed"):
            self.apply(manifest, receipt)

    def test_portable_registry_contains_complete_structural_skillset(self):
        path = SCRIPT.parent / "check_structure.py"
        spec = importlib.util.spec_from_file_location("takeover_structure", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        files = set(TOOL.portable_files(SCRIPT.parents[2]))
        for name in module.REQUIRED_SKILLS:
            self.assertIn(f".claude/skills/{name}/SKILL.md", files)
            self.assertIn(f".agents/skills/{name}/SKILL.md", files)

    def test_staging_matches_result_keeps_target_intact_and_excludes_secrets(self):
        original = (self.root / "AGENTS.md").read_bytes()
        manifest, plan, receipt = self.prepare()
        directory = self.session / "staging"
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), original)
        self.assertIn("Preserve business rules", (directory / "AGENTS.md").read_text())
        self.assertEqual((directory / "new/deep.txt").read_text(), "new document\n")
        self.assertFalse((directory / ".env").exists())
        self.assertFalse((self.root / "new/deep.txt").exists())
        self.assertIsNotNone(TOOL.check_stage(self.session, manifest, plan)["validation"])
        (directory / "AGENTS.md").write_text("tampered staged result\n")
        with self.assertRaisesRegex(ValueError, "staged result changed"):
            self.apply(manifest, receipt)
        self.assertFalse((self.session / "journal.json").exists())

    def test_staging_rebuilds_amended_unapproved_plan_and_requires_evidence(self):
        manifest, plan, _ = self.prepare()
        (self.session / "approval.json").unlink()
        plan["operations"][0]["content"] += "amended\n"
        TOOL.save(self.session / "plan.json", plan)
        TOOL.stage(self.session, manifest, self.root)
        with self.assertRaisesRegex(ValueError, "staging validation"):
            TOOL.seal(self.session, manifest, self.root, "accepted")
        TOOL.stage_check(self.session, manifest, self.root, "fixture fingerprint validation passed")
        receipt = TOOL.seal(self.session, manifest, self.root, "accepted amended diff")
        self.assertEqual(self.apply(manifest, receipt)["status"], "APPLIED")

    def test_unreviewed_staging_symlink_and_changed_evidence_block(self):
        manifest, _, receipt = self.prepare()
        directory = self.session / "staging"
        (directory / "service").mkdir()
        (directory / "service/AGENTS.md").symlink_to(self.root / "AGENTS.md")
        with self.assertRaisesRegex(ValueError, "unreviewed workflow"):
            self.apply(manifest, receipt)
        (directory / "service/AGENTS.md").unlink()
        staged = TOOL.load(self.session / "staged.json")
        staged["validation"] = "changed evidence"
        TOOL.save(self.session / "staged.json", staged)
        with self.assertRaisesRegex(ValueError, "staging evidence changed"):
            self.apply(manifest, receipt)

    def test_added_private_staging_settings_block_without_reading_them(self):
        manifest, _, receipt = self.prepare()
        private = self.session / "staging/.claude/settings.local.json"
        private.parent.mkdir(exist_ok=True)
        private.write_text('{"hooks":{"unexpected":[]}}')
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            self.apply(manifest, receipt)

    def test_new_active_symlink_invalidates_approved_coverage(self):
        manifest, _, receipt = self.prepare()
        external = self.base / "external-rules.md"
        external.write_text("new workflow authority\n")
        (self.root / "service").mkdir()
        (self.root / "service/AGENTS.md").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "file set changed"):
            self.apply(manifest, receipt)
        self.assertFalse((self.session / "journal.json").exists())

    def test_generated_python_caches_do_not_invalidate_reapply(self):
        manifest, _, receipt = self.prepare()
        self.apply(manifest, receipt)
        cache = self.root / ".lean/scripts/__pycache__"
        cache.mkdir(parents=True)
        (cache / "generated.pyc").write_bytes(b"generated cache")
        self.assertEqual(self.apply(manifest, receipt)["status"], "APPLIED")

    def test_real_baseline_install_passes_target_checks_preserves_facts_and_rollback(self):
        baseline = SCRIPT.parents[2]
        (self.root / ".lean").mkdir()
        facts = "# Actual target\n\n<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n"
        config = '{"mode":"standard","configured":true,"execution":"direct","custom":"retained"}\n'
        (self.root / ".lean/PROJECT.md").write_text(facts)
        (self.root / ".lean/config.json").write_text(config)
        (self.root / ".gitignore").write_text(".env\n.claude/.gate-cache\n.claude/.gate-failed\n.agent-runtime/\n")
        (self.root / ".claude").mkdir()
        settings = '{"permissions":{"deny":["Read(./private-data/**)"]},"hooks":{}}\n'
        (self.root / ".claude/settings.json").write_text(settings)
        (self.root / "LICENSE").write_text("Target license\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        original = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mode & 0o777)
                    for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}
        manifest = self.init()
        for name, entry in manifest["files"].items():
            if entry["status"] == "unread":
                TOOL.coverage(self.session, manifest, self.root, name, "cover", entry["before"]["sha256"])
        TOOL.draft(self.session, manifest, self.root, baseline)
        plan = TOOL.load(self.session / "plan.json")
        plan.update(unresolved=[], acceptance=["Installed structure and mode checks pass; target facts/permissions/license retained"])
        plan["rule_map"] = [{"source": "AGENTS.md", "rule": "preserve business rules",
                             "destination": "AGENTS.md Project additions", "reason": "fixture accepted rule"}]
        for op in plan["operations"]:
            if op["path"] == "AGENTS.md":
                op["content"] += "Preserve business rules\n"
        paths = {op["path"] for op in plan["operations"]}
        plan["dispositions"] = [{"path": name, "action": "replace" if name in paths else "keep", "reason": "fixture preservation"}
                                for name, entry in manifest["files"].items() if entry["status"] == "read"]
        TOOL.save(self.session / "plan.json", plan)
        receipt = self.seal_ready(manifest, "fixture accepted installation diff", real_checks=True)
        self.cli("apply", "--session", str(self.session), "--approval", receipt["plan_sha256"])
        for command in (["bash", ".lean/scripts/check-structure.sh"], ["python3", ".lean/scripts/workflow.py", "check"]):
            result = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / ".lean/PROJECT.md").read_text(), facts)
        self.assertEqual((self.root / ".lean/config.json").read_text(), config)
        self.assertEqual((self.root / ".claude/settings.json").read_text(), settings)
        self.assertEqual((self.root / "LICENSE").read_text(), "Target license\n")
        # An already identical installation is a no-op after reconciling project additions.
        next_session = self.base / "second session"
        TOOL.initial(self.root, next_session)
        next_manifest = TOOL.load(next_session / "inventory.json")
        for name, entry in next_manifest["files"].items():
            if entry["status"] == "unread":
                TOOL.coverage(next_session, next_manifest, self.root, name, "cover", entry["before"]["sha256"])
        TOOL.draft(next_session, next_manifest, self.root, baseline)
        next_plan = TOOL.load(next_session / "plan.json")
        self.assertEqual([op["path"] for op in next_plan["operations"]], ["AGENTS.md"])
        next_plan.update(operations=[], unresolved=[], acceptance=["No-op; project rules retained"])
        next_plan["dispositions"] = [{"path": name, "action": "keep", "reason": "identical baseline or project-owned"}
                                     for name, entry in next_manifest["files"].items() if entry["status"] == "read"]
        TOOL.save(next_session / "plan.json", next_plan)
        next_receipt = self.seal_ready(next_manifest, "fixture accepted no-op", session=next_session, real_checks=True)
        self.assertEqual(TOOL.apply_plan(next_session, next_manifest, self.root, next_receipt["plan_sha256"])["operations"], 0)
        self.cli("rollback", "--session", str(self.session))
        after = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mode & 0o777)
                 for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts and ".agent-runtime" not in p.parts}
        self.assertEqual(after, original)


if __name__ == "__main__":
    unittest.main()
