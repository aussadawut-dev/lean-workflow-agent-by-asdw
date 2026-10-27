import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patcher import apply_patch

B = "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n"
CASES = [
    ("replace", "a\nb\nc\n", "@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n", "a\nB\nc\n"),
    ("headers ignored", "a\nb\n", "diff --git a/f b/f\nindex 1..2 100644\n--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n-a\n+A\n b\n", "A\nb\n"),
    ("section text", "a\nb\n", "@@ -1,2 +1,2 @@ def f():\n-a\n+A\n b\n", "A\nb\n"),
    ("omitted counts", "a\n", "@@ -1 +1 @@\n-a\n+b\n", "b\n"),
    ("insert top", "a\n", "@@ -0,0 +1,2 @@\n+x\n+y\n", "x\ny\na\n"),
    ("create file", "", "--- /dev/null\n+++ b/f\n@@ -0,0 +1,2 @@\n+x\n+y\n", "x\ny\n"),
    ("delete all", "x\ny\n", "@@ -1,2 +0,0 @@\n-x\n-y\n", ""),
    ("insert after line 2", "a\nb\nc\n", "@@ -2,0 +3,1 @@\n+X\n", "a\nb\nX\nc\n"),
    ("two hunks shift", B, "@@ -1,2 +1,3 @@\n 1\n+1.5\n 2\n@@ -8,2 +9,1 @@\n 8\n-9\n", "1\n1.5\n2\n3\n4\n5\n6\n7\n8\n10\n"),
    ("offset forward", "z\nz\n" + B, "@@ -2,3 +2,3 @@\n 2\n-3\n+III\n 4\n", "z\nz\n1\n2\nIII\n4\n5\n6\n7\n8\n9\n10\n"),
    ("offset backward", B.replace("1\n2\n", "", 1), "@@ -5,3 +5,3 @@\n 5\n-6\n+VI\n 7\n", "3\n4\n5\nVI\n7\n8\n9\n10\n"),
    ("nearest of two", "x\na\nx\nb\nx\n", "@@ -3,1 +3,1 @@\n-x\n+Y\n", "x\na\nY\nb\nx\n"),
    ("tie prefers +1", "x\nq\nm\nq\nx\n", "@@ -3,1 +3,1 @@\n-q\n+Q\n", "x\nq\nm\nQ\nx\n"),
    ("never before previous hunk", "a\nb\na\nb\n", "@@ -1,1 +1,1 @@\n-a\n+A\n@@ -1,1 +1,1 @@\n-b\n+B\n", "A\nB\na\nb\n"),
    ("add missing final newline", "a\nb", "@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+b\n", "a\nb\n"),
    ("remove final newline", "a\nb\n", "@@ -1,2 +1,2 @@\n a\n-b\n+b\n\\ No newline at end of file\n", "a\nb"),
    ("context without final newline", "a\nb", "@@ -1,2 +1,3 @@\n+z\n a\n b\n\\ No newline at end of file\n", "z\na\nb"),
    ("empty body line is context", "a\n\nb\n", "@@ -1,3 +1,3 @@\n a\n\n-b\n+B\n", "a\n\nB\n"),
    ("empty context with space", "a\n\nb\n", "@@ -1,3 +1,3 @@\n a\n \n-b\n+B\n", "a\n\nB\n"),
    ("trailing whitespace matters", "a \nb\n", "@@ -1,2 +1,2 @@\n a \n-b\n+B\n", "a \nB\n"),
    ("plus/minus text", "-x\n+y\n", "@@ -1,2 +1,2 @@\n--x\n++X\n +y\n", "+X\n+y\n"),
    ("no hunks", "a\n", "--- a/f\n+++ b/f\n", "a\n"),
    ("three hunks", B, "@@ -1 +1 @@\n-1\n+one\n@@ -5 +5 @@\n-5\n+five\n@@ -10 +10 @@\n-10\n+ten\n", B.replace("1\n", "one\n", 1).replace("5\n", "five\n").replace("10\n", "ten\n")),
]
ERRORS = [
    ("count too small", "a\nb\n", "@@ -1,1 +1,1 @@\n a\n-b\n+B\n"),
    ("count too large", "a\nb\n", "@@ -1,3 +1,3 @@\n a\n-b\n+B\n"),
    ("no match", "a\nb\n", "@@ -1,2 +1,2 @@\n a\n-c\n+C\n"),
    ("newline state mismatch", "a\nb\n", "@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+B\n"),
    ("only before previous", "a\nb\nc\n", "@@ -2,1 +2,1 @@\n-b\n+B\n@@ -1,1 +1,1 @@\n-a\n+A\n"),
    ("bad prefix", "a\n", "@@ -1 +1 @@\n*a\n"),
    ("bad header", "a\n", "@@ -x +1 @@\n-a\n+b\n"),
]


class Hidden(unittest.TestCase):
    def test_cases(self):
        for name, original, patch, expected in CASES:
            with self.subTest(case=name):
                self.assertEqual(apply_patch(original, patch), expected)

    def test_errors(self):
        for name, original, patch in ERRORS:
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    apply_patch(original, patch)


if __name__ == "__main__":
    unittest.main()
