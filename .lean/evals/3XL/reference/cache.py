"""A small thread-safe LRU cache with single-flight loading."""
from collections import OrderedDict
import threading


class _Load:
    def __init__(self):
        self.done = threading.Event()
        self.value = None
        self.error = None


class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._items = OrderedDict()
        self._loads = {}
        self._lock = threading.Lock()

    def _store(self, key, value):
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def get(self, key):
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key, value):
        with self._lock:
            self._store(key, value)

    def get_or_load(self, key, loader):
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
            load = self._loads.get(key)
            owner = load is None
            if owner:
                load = self._loads[key] = _Load()
        if not owner:
            load.done.wait()
            if load.error is not None:
                raise load.error
            return load.value
        try:
            load.value = loader()
        except BaseException as error:
            load.error = error
            with self._lock:
                del self._loads[key]
            load.done.set()
            raise
        with self._lock:
            self._store(key, load.value)
            del self._loads[key]
        load.done.set()
        return load.value

    def __len__(self):
        with self._lock:
            return len(self._items)
