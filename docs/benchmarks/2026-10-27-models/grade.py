"""Run hidden tests in a repo copy and count subtest-level passes: prints JSON {passed, total}."""
import json, sys, unittest, io
from pathlib import Path
repo, hidden = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo))
counts = {"passed": 0, "failed": 0}


class R(unittest.TextTestResult):
    def addSubTest(self, test, sub, err):
        counts["failed" if err else "passed"] += 1
        super().addSubTest(test, sub, err)


loader = unittest.TestLoader()
try:
    suite = loader.discover(str(hidden), pattern="test_hidden*.py", top_level_dir=str(hidden))
    unittest.TextTestRunner(stream=io.StringIO(), resultclass=R).run(suite)
except Exception as error:  # noqa: BLE001 - an unimportable solution scores zero
    print(json.dumps({"passed": 0, "total": int(sys.argv[3]), "error": repr(error)[:200]}))
    raise SystemExit(0)
print(json.dumps({"passed": counts["passed"], "total": int(sys.argv[3])}))
