import ast, sys, unittest, warnings
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import users, api, jobs


class Hidden(unittest.TestCase):
    def test_rename(self):
        with self.subTest(case="new name"):
            self.assertEqual(users.fetch_user(1)["name"], "Ada")
        with self.subTest(case="__all__"):
            self.assertTrue({"fetch_user", "fetch_usr"} <= set(users.__all__))
        for name in ("api.py", "jobs.py", "users.py"):
            with self.subTest(callers=name):
                tree = ast.parse((ROOT / name).read_text())
                calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and getattr(node.func, "id", getattr(node.func, "attr", None)) == "fetch_usr"]
                self.assertEqual(calls, [], "callers still call the old name")

    def test_alias(self):
        with self.subTest(case="alias warns every call"):
            with warnings.catch_warnings(record=True) as seen:
                warnings.simplefilter("always")
                users.fetch_usr(2)
                users.fetch_usr(2)
            self.assertEqual(sum(issubclass(w.category, DeprecationWarning) for w in seen), 2)
        with self.subTest(case="alias result"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.assertEqual(users.fetch_usr(2), users.fetch_user(2))

    def test_behaviour(self):
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            with self.subTest(case="api"):
                self.assertEqual(api.get_profile(3), (404, {}))
                self.assertEqual(api.get_profile(2), (200, {"name": "Lin", "email": "lin@example.com"}))
            with self.subTest(case="jobs"):
                self.assertEqual(jobs.mailing_list([1, 2, 3]), ["ada@example.com", "lin@example.com"])
            with self.subTest(case="display_name"):
                self.assertEqual(users.display_name(9), "unknown")
        with self.subTest(case="no warnings from updated callers"):
            self.assertFalse([w for w in seen if issubclass(w.category, DeprecationWarning)])
