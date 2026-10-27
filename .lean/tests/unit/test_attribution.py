"""Unpushed commits must not carry AI attribution; pushed history and quoting prose are fine."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import git, install, lean  # noqa: E402
from lean import attribution  # noqa: E402

TRAILER = "Co-" + "Authored-By: Someone <x@example.invalid>"
GENERATED = "🤖 Generated " + "with [Claude Code](https://claude.com/claude-code)"


class AttributionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install(self.root)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def commit(self, message):
        (self.root / "file.txt").write_text(message)
        git(self.root, "add", "-A")
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@e.invalid",
                        "commit", "-qm", message], check=True)
        return git(self.root, "rev-parse", "--short", "HEAD")

    def test_an_empty_repository_passes(self):
        self.assertEqual(attribution.check(self.root), "")

    def test_unpushed_attribution_is_refused_and_named(self):
        self.commit("feat: plain")
        bad = self.commit(f"fix: thing\n\n{TRAILER}")
        message = attribution.check(self.root)
        self.assertIn(bad, message)
        result = lean(self.root, "attribution")
        self.assertEqual(result.returncode, 1)
        self.assertIn("AI attribution", result.stderr)
        self.commit(f"docs: x\n\n{GENERATED}")
        self.assertEqual(len(attribution.offending(self.root)), 2)

    def test_prose_mentioning_the_phrase_and_pushed_history_pass(self):
        self.commit("docs: explain that we never add a Co-Authored-By trailer or 'Generated with Claude' lines")
        self.assertEqual(attribution.check(self.root), "")
        self.commit(f"fix: old\n\n{TRAILER}")
        remote = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, remote)
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.root, "fetch", "-q", "origin")
        self.assertEqual(attribution.check(self.root), "", "pushed history cannot be amended")


if __name__ == "__main__":
    unittest.main()
