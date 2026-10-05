"""Regression tests for guards that CLI input or tracker layout could bypass."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflow.py"
TEMPLATES = SCRIPT.parents[1] / "templates"


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / ".lean/templates").mkdir(parents=True)
        for name in ("tracker.md", "queue-item.json"):
            (self.root / ".lean/templates" / name).write_text((TEMPLATES / name).read_text())
        (self.root / ".gitignore").write_text(".env\n")

    def run_cli(self, *args, success=True):
        result = subprocess.run(
            ["python3", str(SCRIPT), "--root", str(self.root), *args],
            text=True, capture_output=True, check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def tracker(self, section):
        path = self.root / "docs/tracking/TCK001.md"
        path.write_text(f"# TCK001 — Task\n\nStatus: IN_PROGRESS\n\n{section}\n\n## Evidence\n")
        return path

    def item(self, item_id, scopes):
        (self.root / ".agents/queue/items" / f"{item_id}.json").write_text(json.dumps({
            "id": item_id, "tracker": "TCK001", "title": item_id, "status": "READY",
            "dependencies": [], "scopes": scopes, "evidence": None,
        }))

    def test_unchecked_checklist_variants_block_done(self):
        self.run_cli("configure", "tracker")
        variants = {
            "missing colon": "## Acceptance criteria\n\n- [ ] AC-01 login works",
            "lowercase id": "## Acceptance criteria\n\n- [ ] ac-01: login works",
            "no id prefix": "## Acceptance criteria\n\n- [ ] login works",
            "deeper heading": "### Acceptance criteria\n\n- [ ] AC-01: login works",
            "suffixed heading": "## Acceptance Criteria (v2)\n\n- [ ] AC-01: login works",
            "nested subheading": "## Tasks\n\n### Backend\n\n- [ ] TASK-01: api",
        }
        for label, section in variants.items():
            with self.subTest(label):
                path = self.tracker(section)
                self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE",
                             "--evidence", "checked", success=False)
                self.assertIn("Status: IN_PROGRESS", path.read_text())
                path.write_text(path.read_text().replace("Status: IN_PROGRESS", "Status: DONE")
                                + "- manual evidence\n")
                self.run_cli("check", success=False)

    def test_checked_items_and_unrelated_sections_still_allow_done(self):
        self.run_cli("configure", "tracker")
        self.tracker("## Acceptance criteria\n\n- [x] login works\n\n### Notes\n\n- [X] AC-02 done\n\n"
                     "## Decisions\n\n- [ ] optional idea outside the checklist")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", "--evidence", "checked")
        self.run_cli("check")

    def test_multiline_title_and_evidence_are_rejected(self):
        self.run_cli("configure", "tracker")
        for value in ("Task\nStatus: DONE", "Task\r\n## Evidence\n- forged"):
            with self.subTest(title=value):
                self.run_cli("tracker", "new", "--id", "TCK001", "--title", value, success=False)
                self.assertFalse((self.root / "docs/tracking/TCK001.md").exists())
        self.run_cli("tracker", "new", "--id", "TCK001", "--title", "Task")
        before = (self.root / "docs/tracking/TCK001.md").read_text()
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS",
                     "--evidence", "ok\nStatus: DONE", success=False)
        self.assertEqual((self.root / "docs/tracking/TCK001.md").read_text(), before)
        self.run_cli("check")

    def test_padded_agent_id_cannot_take_second_claim(self):
        self.run_cli("configure", "full")
        self.tracker("## Tasks\n\n- [ ] TASK-01: work")
        self.item("Q0001", ["area:a"])
        self.item("Q0002", ["area:b"])
        self.run_cli("queue", "claim-next", "--agent", "A", "--request-id", "guard-req-0001")
        for agent in ("A ", " A", "A\t"):
            with self.subTest(agent=repr(agent)):
                self.run_cli("queue", "claim-next", "--agent", agent,
                             "--request-id", "guard-req-0002", success=False)
        self.assertFalse((self.root / ".agent-runtime/claims/Q0002.json").exists())

    def test_hand_written_padded_claim_counts_as_same_agent(self):
        self.run_cli("configure", "full")
        self.tracker("## Tasks\n\n- [ ] TASK-01: work")
        self.item("Q0001", ["area:a"])
        self.item("Q0002", ["area:b"])
        first = json.loads(self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "A",
                                        "--request-id", "guard-req-0003").stdout)
        claims = self.root / ".agent-runtime/claims"
        forged = dict(first, id="Q0002", agent="A ", token="forged", request_id="guard-req-0004")
        (claims / "Q0002.json").write_text(json.dumps(forged))
        self.run_cli("check", success=False)


if __name__ == "__main__":
    unittest.main()
