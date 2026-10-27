"""A small in-memory key-value store with JSON persistence and key expiry."""
import json
import math
import numbers
import time


class KVStore:
    def __init__(self, clock=time.time):
        self._clock = clock
        self._data = {}
        self._expiry = {}

    def _live(self, key):
        at = self._expiry.get(key)
        if at is not None and self._clock() >= at:
            self._data.pop(key, None)
            self._expiry.pop(key, None)
        return key in self._data

    def set(self, key, value, ttl=None):
        if ttl is not None:
            if isinstance(ttl, bool) or not isinstance(ttl, numbers.Real) or not ttl > 0:
                raise ValueError("ttl must be a positive number of seconds")
        self._data[key] = value
        if ttl is None:
            self._expiry.pop(key, None)
        else:
            self._expiry[key] = self._clock() + ttl

    def get(self, key):
        return self._data[key] if self._live(key) else None

    def delete(self, key):
        if not self._live(key):
            return False
        del self._data[key]
        self._expiry.pop(key, None)
        return True

    def keys(self):
        return sorted(key for key in list(self._data) if self._live(key))

    def ttl(self, key):
        if not self._live(key):
            return -2
        at = self._expiry.get(key)
        return -1 if at is None else math.ceil(at - self._clock())

    def save(self, path):
        live = self.keys()
        with open(path, "w") as handle:
            json.dump({"version": 2, "data": {k: self._data[k] for k in live},
                       "expiry": {k: self._expiry[k] for k in live if k in self._expiry}}, handle)

    @classmethod
    def load(cls, path, clock=time.time):
        store = cls(clock)
        with open(path) as handle:
            raw = json.load(handle)
        store._data = dict(raw["data"])
        store._expiry = {k: float(v) for k, v in raw.get("expiry", {}).items() if k in store._data}
        return store
