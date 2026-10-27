"""A small in-memory key-value store with JSON persistence."""
import json
import time


class KVStore:
    def __init__(self, clock=time.time):
        self._clock = clock
        self._data = {}

    def set(self, key, value):
        self._data[key] = value

    def get(self, key):
        return self._data.get(key)

    def delete(self, key):
        return self._data.pop(key, None) is not None

    def keys(self):
        return sorted(self._data)

    def save(self, path):
        with open(path, "w") as handle:
            json.dump({"version": 1, "data": self._data}, handle)

    @classmethod
    def load(cls, path, clock=time.time):
        store = cls(clock)
        with open(path) as handle:
            store._data = dict(json.load(handle)["data"])
        return store
