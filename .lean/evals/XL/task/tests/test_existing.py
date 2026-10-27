import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kv.store import KVStore
from kv.cli import main


class Existing(unittest.TestCase):
    def test_store(self):
        store = KVStore()
        store.set("a", "1")
        self.assertEqual(store.get("a"), "1")
        self.assertEqual(store.keys(), ["a"])
        self.assertTrue(store.delete("a"))
        self.assertFalse(store.delete("a"))

    def test_persistence(self):
        store = KVStore()
        store.set("a", "1")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "db.json"
            store.save(path)
            self.assertEqual(KVStore.load(path).get("a"), "1")

    def test_cli(self):
        store = KVStore()
        self.assertEqual(main(["set", "a", "1"], store), (0, "OK"))
        self.assertEqual(main(["get", "a"], store), (0, "1"))
        self.assertEqual(main(["get", "b"], store), (1, "(nil)"))
        self.assertEqual(main(["frob"], store)[0], 2)


if __name__ == "__main__":
    unittest.main()
