import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from semver import compare

ORDER = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
         "1.0.0-rc.1", "1.0.0"]
EQUAL = [("1.0.0+build", "1.0.0"), ("1.0.0-alpha+001", "1.0.0-alpha"), ("1.0.0+a.b", "1.0.0+c"),
         ("1.0.0-x-y-z.--+exp.sha.5114f85", "1.0.0-x-y-z.--")]
LESS = [("0.9.9", "1.0.0"), ("1.9.0", "1.10.0"), ("1.10.0", "1.11.0"), ("2.1.0", "2.1.1"),
        ("1.0.0-1", "1.0.0-a"), ("1.0.0-2", "1.0.0-10"), ("1.0.0-a.1", "1.0.0-a.1.0"), ("1.0.0-A", "1.0.0-a"),
        ("1.0.0-0", "1.0.0-0a"), ("1.0.0-rc.9", "1.0.0-rc.10"), ("1.0.0-alpha.9", "1.0.0-alpha.x")]
INVALID = ["1", "1.2", "1.2.3.4", "01.2.3", "1.02.3", "1.2.03", "1.2.3-", "1.2.3-01", "1.2.3-a..b", "1.2.3+",
           "1.2.3+a..b", "v1.2.3", " 1.2.3", "1.2.3 ", "1.2.3-α", "-1.2.3", "1.2.3-a+b+c", ""]
VALID_ODD = ["1.2.3-0", "1.2.3-0a", "1.2.3-a-b", "1.2.3+01", "1.2.3--", "0.0.0", "1.2.3-0.0.1", "99999999999999999999.0.0"]


class Hidden(unittest.TestCase):
    def test_order_chain(self):
        for i, low in enumerate(ORDER):
            for high in ORDER[i + 1:]:
                with self.subTest(low=low, high=high):
                    self.assertEqual(compare(low, high), -1)
                    self.assertEqual(compare(high, low), 1)

    def test_equal_ignoring_build(self):
        for a, b in EQUAL:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare(a, b), 0)

    def test_less(self):
        for a, b in LESS:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare(a, b), -1)
                self.assertEqual(compare(b, a), 1)

    def test_invalid(self):
        for bad in INVALID:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    compare(bad, "1.0.0")
                with self.assertRaises(ValueError):
                    compare("1.0.0", bad)

    def test_valid_odd(self):
        for good in VALID_ODD:
            with self.subTest(good=good):
                self.assertIn(compare(good, good), (0,))

    def test_not_bool_or_none(self):
        for bad in (None, 1, b"1.0.0"):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, TypeError)):
                    compare(bad, "1.0.0")


if __name__ == "__main__":
    unittest.main()
