"""Smoke the distributable filesystem as a new project without copying runtime state."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def bootstrap(root):
    listing = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
    for name in set(listing.decode().split("\0")):
        source = ROOT / name
        # A working-tree move can leave retired index entries beneath a link.
        # Never materialize their dereferenced content as provider-owned copies.
        if any((ROOT / parent).is_symlink() for parent in Path(name).parents):
            continue
        reusable = name.startswith((".lean/", ".claude/", ".agents/skills/")) or name in ("AGENTS.md", "CLAUDE.md", ".gitignore")
        project_owned = name in (".lean/config.json", ".lean/PROJECT.md", ".lean/model-catalog.json")
        if reusable and not project_owned and source.is_symlink():
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(source.readlink(), target_is_directory=True)
        elif reusable and not project_owned and source.is_file():
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if name in ("AGENTS.md", "CLAUDE.md"):
                destination.write_text(source.read_text().split("## Project additions", 1)[0] + "## Project additions\n\n")
    # The installed self-tests must not assert the host project's defaults,
    # records, license or application gate. Build an isolated starter fixture.
    (root / ".lean/config.json").write_text(json.dumps({"mode": "standard", "configured": False, "execution": "direct"}))
    (root / ".lean/PROJECT.md").write_text("# Test project\n\n<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
    (root / "LICENSE").write_text("Separate project license\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)


class TemplateSmokeTests(unittest.TestCase):
    def test_fresh_copy_setup_and_full_workset_lifecycle(self):
        with tempfile.TemporaryDirectory(prefix="lean new project ") as directory:
            root = Path(directory)
            bootstrap(root)

            def run(*args):
                result = subprocess.run(args, cwd=root, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            script = str(root / ".lean/scripts/workflow.py")
            initial = json.loads(run("python3", script, "show"))
            self.assertEqual(initial, {"mode": "standard", "configured": False, "execution": "direct"})
            self.assertFalse((root / "docs/tracking").exists())
            self.assertFalse((root / ".agents/queue").exists())
            self.assertFalse((root / ".agent-runtime").exists())
            self.assertIn("MIT License", (root / ".lean/LICENSE").read_text())
            self.assertEqual((root / "LICENSE").read_text(), "Separate project license\n")
            run("bash", str(root / ".lean/scripts/check-structure.sh"))
            run("python3", script, "check")
            run("python3", script, "configure", "standard")
            self.assertFalse((root / "docs/tracking").exists())
            run("python3", script, "configure", "tracker", "--execution", "delegated")
            run("python3", script, "tracker", "new", "--id", "TCK001", "--title", "New project smoke")
            tracker = root / "docs/tracking/TCK001.md"
            tracker.write_text(tracker.read_text().replace("- [ ]", "- [x]"))
            run("python3", script, "check")
            run("python3", script, "configure", "full")
            self.assertEqual(json.loads(run("python3", script, "show"))["execution"], "delegated")
            item = json.loads((root / ".lean/templates/queue-item.json").read_text())
            (root / ".agents/queue/items/Q0001.json").write_text(json.dumps(item))
            claim = json.loads(run("python3", script, "queue", "claim", "--id", "Q0001", "--agent", "smoke",
                                   "--request-id", "smoke-request-00001"))
            run("python3", script, "queue", "complete", "--id", "Q0001", "--token", claim["token"],
                "--evidence", "smoke validation passed")
            run("python3", script, "tracker", "status", "--id", "TCK001", "--status", "DONE",
                "--evidence", "smoke review passed")
            run("python3", script, "check")
            run("bash", str(root / ".lean/scripts/check-structure.sh"))


    def test_installed_smoke_survives_onboarding_and_project_license(self):
        for mode in ("standard", "tracker", "full"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="lean configured project ") as directory:
                root = Path(directory)
                bootstrap(root)
                subprocess.run(["python3", str(root / ".lean/scripts/workflow.py"), "configure", mode], check=True, capture_output=True)
                (root / "LICENSE").write_text("Project-owned license placeholder\n")
                (root / "application-guide.md").write_text("Existing project instructions\n")
                with (root / "AGENTS.md").open("a") as output:
                    output.write("\n@application-guide.md\n")
                records = {}
                if mode in ("tracker", "full"):
                    subprocess.run(["python3", str(root / ".lean/scripts/workflow.py"), "tracker", "new",
                                    "--id", "TCK998", "--title", "Existing project work"], check=True, capture_output=True)
                    tracker = root / "docs/tracking/TCK998.md"
                    records[tracker] = tracker.read_text()
                if mode == "full":
                    item = json.loads((root / ".lean/templates/queue-item.json").read_text())
                    item.update(id="Q0999", tracker="TCK998")
                    path = root / ".agents/queue/items/Q0999.json"
                    path.write_text(json.dumps(item))
                    records[path] = path.read_text()
                before = (root / ".lean/config.json").read_text()
                result = subprocess.run(["python3", str(root / ".lean/tests/test_template.py"),
                                         "TemplateSmokeTests.test_fresh_copy_setup_and_full_workset_lifecycle"],
                                        cwd=root, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                structure = subprocess.run(["python3", "-m", "unittest", "discover", "-s", ".lean/tests", "-p", "test_structure.py"],
                                           cwd=root, text=True, capture_output=True)
                self.assertEqual(structure.returncode, 0, structure.stdout + structure.stderr)
                self.assertEqual((root / ".lean/config.json").read_text(), before)
                self.assertEqual((root / "LICENSE").read_text(), "Project-owned license placeholder\n")
                for path, content in records.items():
                    self.assertEqual(path.read_text(), content)

if __name__ == "__main__":
    unittest.main()
