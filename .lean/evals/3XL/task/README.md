# Task

`cache.LRUCache.get_or_load` is slow under load and deadlocks when a loader uses the cache itself. Rework
`cache.py` so that, with the same public API (`LRUCache(capacity)`, `get`, `put`, `get_or_load`, `len()`):

1. Concurrent `get_or_load(key, loader)` calls for the same missing key run `loader()` once; every caller
   gets its result.
2. Loads of different keys run in parallel: one slow loader never blocks other keys, `get` or `put`.
3. A loader may call the cache (for other keys) without deadlocking.
4. If the loader raises, every caller waiting for that load gets the same exception and nothing is cached;
   the next `get_or_load` for the key runs the loader again.
5. The cache never holds more than `capacity` entries, evicting the least recently used; `get` and a hit in
   `get_or_load` count as a use. `get` of a missing key returns `None`.
6. Everything is thread-safe.

`python3 -m unittest discover -s tests` runs the visible tests.
