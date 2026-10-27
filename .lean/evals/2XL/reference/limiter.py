"""Request rate limiting: a sliding window per key (docs/limits.md)."""
from collections import deque, namedtuple
import time

Decision = namedtuple("Decision", "allowed retry_after")


class Limiter:
    def __init__(self, limit, window, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._seen = {}

    def check(self, key):
        now = self.clock()
        times = self._seen.setdefault(key, deque())
        while times and times[0] <= now - self.window:
            times.popleft()
        if len(times) < self.limit:
            times.append(now)
            return Decision(True, 0.0)
        return Decision(False, times[0] + self.window - now)

    def allow(self, key):
        return self.check(key).allowed
