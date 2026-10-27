import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kv.store import KVStore
from kv.cli import main


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class Hidden(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.store = KVStore(clock=self.clock)

    def test_expiry(self):
        self.store.set("a", "1", ttl=10)
        with self.subTest(case="alive before expiry"):
            self.clock.now = 1009.9
            self.assertEqual(self.store.get("a"), "1")
        with self.subTest(case="ttl rounds up"):
            self.assertEqual(self.store.ttl("a"), 1)
        with self.subTest(case="expired at the boundary"):
            self.clock.now = 1010.0
            self.assertIsNone(self.store.get("a"))
            self.assertEqual(self.store.keys(), [])
            self.assertFalse(self.store.delete("a"))
            self.assertEqual(self.store.ttl("a"), -2)

    def test_ttl_values_and_reset(self):
        self.store.set("p", "1")
        with self.subTest(case="no expiry is -1"):
            self.assertEqual(self.store.ttl("p"), -1)
        with self.subTest(case="missing is -2"):
            self.assertEqual(self.store.ttl("nope"), -2)
        with self.subTest(case="set again clears expiry"):
            self.store.set("p", "2", ttl=5)
            self.store.set("p", "3")
            self.clock.now += 100
            self.assertEqual((self.store.get("p"), self.store.ttl("p")), ("3", -1))
        for bad in (0, -1, "5"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.store.set("x", "1", ttl=bad)

    def test_persistence(self):
        self.store.set("keep", "1", ttl=100)
        self.store.set("gone", "2", ttl=1)
        self.store.set("forever", "3")
        self.clock.now += 5
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "db.json"
            self.store.save(path)
            with self.subTest(case="expired not written"):
                self.assertNotIn("gone", path.read_text())
            later = Clock(self.clock.now + 50)
            loaded = KVStore.load(path, clock=later)
            with self.subTest(case="absolute expiry kept"):
                self.assertEqual((loaded.get("keep"), loaded.ttl("keep")), ("1", 45))
            with self.subTest(case="no-expiry kept"):
                self.assertEqual(loaded.ttl("forever"), -1)
            later.now += 100
            with self.subTest(case="expires after load"):
                self.assertIsNone(loaded.get("keep"))
            old = Path(folder) / "old.json"
            old.write_text(json.dumps({"version": 1, "data": {"a": "1"}}))
            with self.subTest(case="old file loads"):
                self.assertEqual(KVStore.load(old, clock=later).ttl("a"), -1)

    def test_cli(self):
        with self.subTest(case="set with ttl"):
            self.assertEqual(main(["set", "a", "1", "--ttl", "30"], self.store), (0, "OK"))
            self.assertEqual(main(["ttl", "a"], self.store), (0, "30"))
        with self.subTest(case="ttl of missing"):
            self.assertEqual(main(["ttl", "zz"], self.store), (0, "-2"))
        for bad in ("abc", "0", "-3"):
            with self.subTest(bad_ttl=bad):
                code, output = main(["set", "a", "1", "--ttl", bad], self.store)
                self.assertEqual(code, 2)
                self.assertTrue(output.startswith("error:"))
        with self.subTest(case="existing commands"):
            self.assertEqual(main(["get", "a"], self.store), (0, "1"))
            self.assertEqual(main(["keys"], self.store), (0, "a"))
