import sys, threading, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache import LRUCache

WAIT = 5


def start(target, *args):
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


class Hidden(unittest.TestCase):
    def test_single_flight(self):
        cache, calls, release, results = LRUCache(4), [], threading.Event(), []

        def loader():
            calls.append(1)
            release.wait(WAIT)
            return "v"

        threads = [start(lambda: results.append(cache.get_or_load("k", loader))) for _ in range(5)]
        time.sleep(0.2)
        release.set()
        for thread in threads:
            thread.join(WAIT)
        with self.subTest(case="loader ran once"):
            self.assertEqual(len(calls), 1)
        with self.subTest(case="every caller got the value"):
            self.assertEqual(results, ["v"] * 5)

    def test_parallel_keys_and_no_blocking(self):
        cache, slow_started, release = LRUCache(4), threading.Event(), threading.Event()

        def slow():
            slow_started.set()
            release.wait(WAIT)
            return "slow"

        thread = start(cache.get_or_load, "slow", slow)
        self.assertTrue(slow_started.wait(WAIT))
        began = time.monotonic()
        with self.subTest(case="other key loads while one is slow"):
            self.assertEqual(cache.get_or_load("fast", lambda: "fast"), "fast")
        with self.subTest(case="get and put not blocked"):
            cache.put("p", 1)
            self.assertEqual(cache.get("p"), 1)
            self.assertLess(time.monotonic() - began, 1.0)
        release.set()
        thread.join(WAIT)

    def test_reentrant_loader(self):
        cache, out = LRUCache(4), []

        def outer():
            return cache.get_or_load("inner", lambda: 2) + 1

        thread = start(lambda: out.append(cache.get_or_load("outer", outer)))
        thread.join(WAIT)
        with self.subTest(case="no deadlock"):
            self.assertFalse(thread.is_alive())
            self.assertEqual(out, [3])

    def test_errors(self):
        cache, release, errors, attempts = LRUCache(4), threading.Event(), [], []

        def failing():
            attempts.append(1)
            release.wait(WAIT)
            raise KeyError("boom")

        def call():
            try:
                cache.get_or_load("k", failing)
            except KeyError as error:
                errors.append(error)

        threads = [start(call) for _ in range(3)]
        time.sleep(1.0)  # Long enough for every caller to join the one load, even on a busy machine.
        release.set()
        for thread in threads:
            thread.join(WAIT)
        with self.subTest(case="all waiters get the error"):
            self.assertEqual(len(errors), 3)
            self.assertEqual(len(attempts), 1)
        with self.subTest(case="nothing cached; next call retries"):
            self.assertIsNone(cache.get("k"))
            self.assertEqual(cache.get_or_load("k", lambda: "ok"), "ok")

    def test_lru(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")
        cache.get_or_load("c", lambda: 3)
        with self.subTest(case="least recently used evicted"):
            self.assertIsNone(cache.get("b"))
            self.assertEqual((cache.get("a"), cache.get("c")), (1, 3))
        with self.subTest(case="capacity respected under concurrency"):
            big = LRUCache(3)
            threads = [start(big.get_or_load, i, lambda i=i: i) for i in range(20)]
            for thread in threads:
                thread.join(WAIT)
            self.assertLessEqual(len(big), 3)
        with self.subTest(case="missing get is None"):
            self.assertIsNone(cache.get("zzz"))
