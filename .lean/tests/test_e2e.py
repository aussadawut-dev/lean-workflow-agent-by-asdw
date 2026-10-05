"""One end-to-end lifecycle: standard -> tracker -> full -> back to standard."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflow.py"
TEMPLATES = SCRIPT.parents[1] / "templates"


class EndToEndLifecycleTests(unittest.TestCase):
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

    def show(self):
        return json.loads(self.run_cli("show").stdout)

    def item(self, item_id, scopes, dependencies=()):
        template = json.loads((TEMPLATES / "queue-item.json").read_text())
        template.update(id=item_id, title=item_id, scopes=scopes, dependencies=list(dependencies))
        (self.root / ".agents/queue/items" / f"{item_id}.json").write_text(json.dumps(template))

    def test_full_lifecycle_preserves_records_and_enforces_guards(self):
        self.assertEqual(self.show(), {"mode": "standard", "configured": False, "execution": "direct"})

        # tracker: workset documents with evidence and checklist guards.
        self.run_cli("configure", "tracker", "--execution", "delegated")
        self.run_cli("tracker", "new", "--id", "TCK001", "--title", "Lifecycle")
        self.run_cli("tracker", "new", "--id", "TCK001", "--title", "Duplicate", success=False)
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS")
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE", success=False)
        self.run_cli("check")

        # full: lease-backed claims honour dependencies, tokens and evidence.
        self.run_cli("configure", "full")
        self.assertEqual(self.show()["execution"], "delegated")
        self.item("Q0001", ["area:a"])
        self.item("Q0002", ["area:b"], dependencies=["Q0001"])
        self.run_cli("check")
        first = json.loads(self.run_cli("queue", "claim-next", "--agent", "A",
                                        "--request-id", "lifecycle-a-0001").stdout)
        self.assertEqual(first["id"], "Q0001")
        again = json.loads(self.run_cli("queue", "claim-next", "--agent", "A",
                                        "--request-id", "lifecycle-a-0001").stdout)
        self.assertEqual(again["token"], first["token"])
        self.run_cli("queue", "claim", "--id", "Q0001", "--agent", "B",
                     "--request-id", "lifecycle-b-0001", success=False)
        self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "B",
                     "--request-id", "lifecycle-b-0002", success=False)
        self.run_cli("queue", "heartbeat", "--id", "Q0001", "--token", first["token"])
        self.run_cli("queue", "heartbeat", "--id", "Q0001", "--token", "wrong", success=False)
        self.run_cli("downgrade", "tracker", "--dry-run", "--keep-pending", success=False)
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", first["token"],
                     "--evidence", "", success=False)
        self.run_cli("queue", "complete", "--id", "Q0001", "--token", first["token"],
                     "--evidence", "lifecycle validation passed")
        second = json.loads(self.run_cli("queue", "claim", "--id", "Q0002", "--agent", "B",
                                         "--request-id", "lifecycle-b-0003").stdout)
        self.run_cli("queue", "release", "--id", "Q0002", "--token", second["token"])
        self.run_cli("check")

        # clean-queue archives DONE items into history and keeps unfinished work.
        self.run_cli("clean-queue", "all", "--apply")
        self.assertFalse((self.root / ".agents/queue/items/Q0001.json").exists())
        self.assertTrue((self.root / ".agents/queue/items/Q0002.json").exists())
        self.assertIn("Q0001", self.run_cli("queue", "history").stdout)
        self.run_cli("check")

        # Downgrades: active trackers block standard; paused work needs acknowledgement.
        self.run_cli("downgrade", "standard", "--dry-run", "--keep-pending", success=False)
        self.run_cli("downgrade", "tracker", "--apply", success=False)
        self.run_cli("downgrade", "tracker", "--apply", "--keep-pending")
        self.assertEqual(self.show()["mode"], "tracker")
        self.run_cli("check")
        tracker = self.root / "docs/tracking/TCK001.md"
        tracker.write_text(tracker.read_text().replace("- [ ]", "- [x]"))
        self.run_cli("tracker", "status", "--id", "TCK001", "--status", "DONE",
                     "--evidence", "lifecycle ok")
        self.run_cli("downgrade", "standard", "--apply", success=False)
        self.run_cli("downgrade", "standard", "--apply", "--keep-pending")
        self.assertEqual(self.show(), {"mode": "standard", "configured": True, "execution": "delegated"})
        self.run_cli("check")
        self.assertIn("Status: DONE", tracker.read_text())
        self.assertTrue((self.root / ".agents/queue/items/Q0002.json").exists())


if __name__ == "__main__":
    unittest.main()
