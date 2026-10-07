"""Real Git acquisition without target writes; release selection and preservation guards."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/update_workflow.py"
spec = importlib.util.spec_from_file_location("update_workflow", SCRIPT)
TOOL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TOOL)


class UpdateWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean update ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.remote = self.base / "remote"
        self.target = self.base / "target"
        self.remote.mkdir()
        self.target.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.remote / ".lean").mkdir()
        (self.remote / ".lean/assets.json").write_text(json.dumps({"schema": 1, "files": ["AGENTS.md", ".lean/assets.json"]}))
        self.old = self.release("1.0.0")
        (self.target / "AGENTS.md").write_text("Lean Workflow Baseline 1.0.0\n## Project additions\nBusiness rules\n")
        (self.target / ".lean").mkdir()
        for name, content in ((".lean/PROJECT.md", "application gate"), (".lean/config.json", '{"mode":"full"}'),
                              ("pending.txt", "uncommitted work"), (".lean/model-catalog.json", "research")):
            (self.target / name).write_text(content)
        self.before = self.snapshot()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.remote, text=True).strip()

    def release(self, version, tag=None):
        (self.remote / "AGENTS.md").write_text("Lean Workflow Baseline " + version + "\n## Project additions\nUpstream-only facts\n")
        self.git("add", ".")
        self.git("commit", "-qm", "release " + version)
        self.git("tag", "-a", tag or "v" + version, "-m", "release")
        return self.git("rev-parse", "HEAD")

    def snapshot(self):
        return {p.relative_to(self.target).as_posix(): p.read_bytes() for p in self.target.rglob("*") if p.is_file()}

    def prepare(self, **kwargs):
        return TOOL.prepare(self.target, self.base / "workspace", str(self.remote), **kwargs)

    def test_stable_numeric_selection_annotated_pin_and_preservation(self):
        self.release("1.9.0")
        newest = self.release("1.10.0")
        self.release("2.0.0", "v2.0.0-rc.1")
        result = self.prepare(installed_ref="v1.0.0")
        self.assertEqual(result["commit"], newest)
        self.assertEqual(result["ref"], "refs/tags/v1.10.0")
        self.assertEqual(result["previous"]["commit"], self.old)
        self.assertEqual(self.snapshot(), self.before)
        self.assertFalse((self.target / ".agent-runtime").exists())
        self.assertEqual(json.loads((self.base / "workspace/release.json").read_text()), result)

    def test_acquisition_to_guarded_apply_and_rollback_preserves_project(self):
        self.release("1.1.0")
        report = self.prepare()
        recovery = TOOL.takeover
        session = Path(report["migration_session"])
        recovery.initial(self.target, session)
        manifest = recovery.load(session / "inventory.json")
        for name, entry in manifest["files"].items():
            if entry["status"] == "unread":
                recovery.coverage(session, manifest, self.target, name, "cover", entry["before"]["sha256"])
        recovery.draft(session, manifest, self.target, report["baseline"])
        plan = recovery.load(session / "plan.json")
        plan["unresolved"] = []
        plan["acceptance"] = ["Retain exact project additions and project data; recovery refuses drift"]
        plan["rule_map"] = [{"source": "AGENTS.md", "rule": "Business rules",
                             "destination": "AGENTS.md Project additions", "reason": "preserve fixture contract"}]
        for operation in plan["operations"]:
            if operation["path"] == "AGENTS.md":
                operation["content"] += self.before["AGENTS.md"].decode().split("## Project additions\n", 1)[1]
        plan["operations"].append({"path": ".lean/upstream.json", "before": None,
            "content": json.dumps(report["provenance"]), "mode": 420, "reason": "pinned project provenance"})
        paths = {op["path"] for op in plan["operations"]}
        plan["dispositions"] = [{"path": name, "action": "replace" if name in paths else "keep",
                                 "reason": "fixture reviewed preservation"}
                                for name, entry in manifest["files"].items() if entry["status"] == "read"]
        recovery.save(session / "plan.json", plan)
        stage = Path(recovery.stage(session, manifest, self.target)["directory"])
        self.assertIn("Business rules", (stage / "AGENTS.md").read_text())
        recovery.stage_check(session, manifest, self.target, "Fixture staged content checks passed; synthetic source has no executable checks")
        receipt = recovery.seal(session, manifest, self.target, "Fixture user accepted exact upgrade diff")
        (self.target / "AGENTS.md").write_text("subsequent edit")
        with self.assertRaises(ValueError):
            recovery.apply_plan(session, manifest, self.target, receipt["plan_sha256"])
        (self.target / "AGENTS.md").write_bytes(self.before["AGENTS.md"])
        recovery.apply_plan(session, manifest, self.target, receipt["plan_sha256"])
        self.assertIn("Business rules", (self.target / "AGENTS.md").read_text())
        for name, original in self.before.items():
            if name != "AGENTS.md":
                self.assertEqual((self.target / name).read_bytes(), original)
        recovery.rollback(session, manifest, self.target)
        self.assertEqual({name: content for name, content in self.snapshot().items()
                          if not name.startswith(".agent-runtime/")}, self.before)

    def test_same_revision_reports_identical_assets_without_apply(self):
        (self.target / "AGENTS.md").write_bytes((self.remote / "AGENTS.md").read_bytes())
        (self.target / ".lean/assets.json").write_bytes((self.remote / ".lean/assets.json").read_bytes())
        before = self.snapshot()
        result = self.prepare()
        self.assertTrue(all(row["identical"] for row in result["comparison"]))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(result["status"], "INSPECT")

    def test_downgrade_and_inconsistent_tag_refused_without_writes(self):
        self.release("0.9.0", "v2.0.0")
        with self.assertRaisesRegex(ValueError, "older"):
            self.prepare()
        self.assertEqual(self.snapshot(), self.before)
        with self.assertRaisesRegex(ValueError, "versions disagree"):
            self.mismatch()

    def mismatch(self):
        self.release("1.1.0", "v3.0.0")
        return TOOL.prepare(self.target, self.base / "other", str(self.remote))

    def test_ref_ambiguity_prerelease_only_and_explicit_commit(self):
        refs = {"refs/tags/main": self.old, "refs/heads/main": self.old}
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            TOOL.select(refs, "main")
        with self.assertRaisesRegex(ValueError, "no stable"):
            TOOL.select({"refs/tags/v2.0.0-beta": self.old})
        result = self.prepare(requested=self.old)
        self.assertEqual(result["commit"], self.old)

    def test_malformed_provenance_and_unknown_baseline_refused(self):
        (self.target / ".lean/upstream.json").write_text(json.dumps({"schema": 1,
            "source": str(self.remote), "commit": ["invalid"]}))
        with self.assertRaisesRegex(ValueError, "invalid upstream"):
            self.prepare()
        before = self.snapshot()
        (self.remote / ".lean/assets.json").unlink()
        self.release("1.1.0")
        with self.assertRaises(OSError):
            TOOL.prepare(self.target, self.base / "missing-registry", str(self.remote))
        self.assertEqual(self.snapshot(), before)

    def test_source_provenance_is_project_owned(self):
        (self.remote / ".lean/upstream.json").write_text('{"commit":"foreign"}')
        (self.remote / ".lean/assets.json").write_text(json.dumps({"schema": 1,
            "files": ["AGENTS.md", ".lean/assets.json", ".lean/upstream.json"]}))
        self.release("1.1.0")
        with self.assertRaisesRegex(ValueError, "project-owned"):
            self.prepare()
        self.assertEqual(self.snapshot(), self.before)

    def test_workspace_boundaries_and_existing_workspace(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            TOOL.prepare(self.target, self.target / "artifacts", str(self.remote))
        with self.assertRaisesRegex(ValueError, "outside"):
            TOOL.prepare(self.target, self.remote / "artifacts", str(self.remote))
        (self.base / "workspace").mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare()
        self.assertEqual(self.snapshot(), self.before)

    def test_provenance_base_and_untrusted_registry(self):
        (self.target / ".lean/upstream.json").write_text(json.dumps({"schema": 1, "source": str(self.remote), "commit": self.old}))
        self.release("1.1.0")
        result = self.prepare()
        self.assertEqual(result["previous"]["commit"], self.old)
        registry = self.remote / ".lean/assets.json"
        registry.write_text(json.dumps({"schema": 1, "files": [".lean/assets.json", ".lean/PROJECT.md"]}))
        (self.remote / ".lean/PROJECT.md").write_text("source facts")
        self.release("1.2.0")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "project-owned"):
            TOOL.prepare(self.target, self.base / "unsafe", str(self.remote))
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
