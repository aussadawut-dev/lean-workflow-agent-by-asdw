"""Shared file helpers."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import support  # noqa: E402,F401
from lean import util  # noqa: E402


class WriteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)

    def test_replacing_a_file_keeps_its_mode(self):
        for mode in (0o644, 0o755, 0o600):
            with self.subTest(mode=oct(mode)):
                path = self.root / f"f{mode:o}"
                path.write_text("old")
                path.chmod(mode)
                util.write_text(path, "new")
                self.assertEqual((path.read_text(), self.mode(path)), ("new", mode))

    def test_a_new_file_gets_the_usual_umask_mode(self):
        previous = os.umask(0o022)
        try:
            util.write_json(self.root / "new.json", {"a": 1})
        finally:
            os.umask(previous)
        self.assertEqual(self.mode(self.root / "new.json"), 0o644)


if __name__ == "__main__":
    unittest.main()
