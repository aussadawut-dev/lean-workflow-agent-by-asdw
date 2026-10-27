"""A small LRU cache."""
from collections import OrderedDict
import threading


class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._items = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key, value):
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)

    def get_or_load(self, key, loader):
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
            value = loader()
            self._items[key] = value
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)
            return value

    def __len__(self):
        with self._lock:
            return len(self._items)
