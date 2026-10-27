# Task

Add key expiry (TTL) to the `kv` key-value store and its command line. Keep the existing behaviour and
tests passing.

Requirements:
1. `KVStore.set(key, value, ttl=None)`: `ttl` is a number of seconds (> 0); `None` means no expiry. A `ttl`
   of 0 or less, or one that is not a number, raises `ValueError`. Setting a key again replaces its value and
   its expiry (no `ttl` means it no longer expires).
2. An expired key behaves as missing everywhere: `get` returns `None`, `keys()` omits it, `delete` returns
   `False`. A key expires when the clock reaches its expiry time.
3. `KVStore.ttl(key)`: seconds left rounded up to a whole number; `-1` for a key without expiry; `-2` for a
   missing or expired key.
4. `save(path)` / `KVStore.load(path, clock=...)` persist expiry as an absolute time; expired keys are not
   written. Files written by the current version (no expiry information) still load.
5. The store takes its time source from the `clock` argument (default `time.time`); tests pass a fake clock.
6. CLI (`kv/cli.py`, `main(argv, store) -> (exit code, output)`): `set KEY VALUE [--ttl SECONDS]` prints `OK`;
   `ttl KEY` prints the number from requirement 3. An invalid `--ttl` gives exit code 2 and a message
   starting with `error:`. The existing commands keep their output.

`python3 -m unittest discover -s tests` runs the visible tests.
