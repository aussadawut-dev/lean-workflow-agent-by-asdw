import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from limiter import Limiter
import api, jobs


class Clock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class Hidden(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.limiter = Limiter(limit=2, window=10, clock=self.clock)

    def at(self, t, key="u"):
        self.clock.now = t
        return self.limiter.check(key)

    def test_sliding_window(self):
        with self.subTest(case="allowed up to the limit"):
            self.assertTrue(self.at(100).allowed and self.at(105).allowed)
        with self.subTest(case="rejected within the window"):
            self.assertFalse(self.at(109.9).allowed)
        with self.subTest(case="not a fixed window"):
            # A fixed 10 s window would reset at 110; the rolling one still holds 105.
            self.assertTrue(self.at(110).allowed)
            self.assertFalse(self.at(112).allowed)

    def test_retry_after_and_rejections_not_counted(self):
        self.at(100), self.at(103)
        with self.subTest(case="retry_after until the oldest leaves"):
            decision = self.at(104)
            self.assertFalse(decision.allowed)
            self.assertAlmostEqual(decision.retry_after, 6.0)
        with self.subTest(case="rejections do not count"):
            for t in (105, 106, 107, 108, 109):
                self.at(t)
            self.assertTrue(self.at(110).allowed)
        with self.subTest(case="boundary: oldest leaves exactly at window"):
            limiter = Limiter(limit=1, window=10, clock=self.clock)
            self.clock.now = 0
            limiter.check("k")
            self.clock.now = 10
            self.assertTrue(limiter.check("k").allowed)

    def test_per_key(self):
        self.at(100, "a"), self.at(100, "a")
        with self.subTest(case="other user unaffected"):
            self.assertTrue(self.at(100, "b").allowed)
        with self.subTest(case="first user still limited"):
            self.assertFalse(self.at(101, "a").allowed)

    def test_callers(self):
        with self.subTest(case="api allows"):
            self.assertEqual(api.handle("x", self.limiter), (200, {"ok": True}))
        with self.subTest(case="api rejects with retry_after"):
            self.clock.now = 101
            api.handle("x", self.limiter)
            self.clock.now = 102
            code, body = api.handle("x", self.limiter)
            self.assertEqual(code, 429)
            self.assertAlmostEqual(body["retry_after"], 8.0)
        with self.subTest(case="allow() kept for jobs"):
            self.assertEqual(len(jobs.run_batch(range(5), Limiter(3, 1, clock=self.clock))), 3)
