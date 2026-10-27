"""Request rate limiting."""
import time


class Limiter:
    def __init__(self, limit, window, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._counts = {}

    def allow(self, key):
        bucket = int(self.clock() // self.window)
        count = self._counts.get((key, bucket), 0)
        self._counts[(key, bucket)] = count + 1
        return count < self.limit
