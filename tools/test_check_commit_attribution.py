import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_commit_attribution import main, offending  # noqa: E402


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                           "-c", "commit.gpgsign=false", *args],
                          cwd=root, check=True, capture_output=True, text=True).stdout.strip()


class CommitAttributionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = Path(self.directory.name)
        self.remote, self.root = base / "remote.git", base / "work"
        git(base, "init", "-q", "--bare", str(self.remote))
        git(base, "init", "-q", "-b", "main", str(self.root))
        git(self.root, "remote", "add", "origin", str(self.remote))

    def tearDown(self):
        self.directory.cleanup()

    def commit(self, message):
        git(self.root, "commit", "-q", "--allow-empty", "-m", message)
        return git(self.root, "rev-parse", "--short", "HEAD")

    def push(self):
        git(self.root, "push", "-q", "origin", "main")

    def test_clean_unpushed_commits_pass(self):
        self.commit("feat: one")
        self.commit("fix: two\n\nBody mentioning co-authors in prose is fine.")
        self.assertEqual(offending(str(self.root)), [])
        self.assertEqual(main(["--root", str(self.root)]), 0)

    def test_unpushed_co_authored_by_trailer_fails(self):
        self.commit("feat: clean")
        bad = self.commit("feat: bad\n\nco-authored-by: Someone <a@example.invalid>")
        self.assertEqual(offending(str(self.root)), [bad])
        self.assertEqual(main(["--root", str(self.root)]), 1)

    def test_generated_with_line_fails(self):
        bad = self.commit("docs: x\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)")
        other = self.commit("docs: y\n\nGenerated with Codex")
        self.assertEqual(sorted(offending(str(self.root))), sorted([bad, other]))

    def test_prose_mentioning_the_attribution_text_passes(self):
        self.commit('feat: rule\n\nFail when a commit carries a "Generated with Claude/Codex" line.\n'
                    '"Generated with Codex" lines are rejected too.')
        self.assertEqual(offending(str(self.root)), [])

    def test_pushed_history_is_not_checked(self):
        self.commit("feat: old\n\nCo-Authored-By: Bot <bot@example.invalid>")
        self.push()
        self.commit("feat: new")
        self.assertEqual(offending(str(self.root)), [])


if __name__ == "__main__":
    unittest.main()
