# Task

Users report that rate limiting does not behave as documented, and `api.py` crashes on every request.
Make the limiter consistent with `docs/limits.md` and with the code that already uses it (`api.py`,
`jobs.py`). Work out what the callers need from the code and the docs; keep existing callers working.

`python3 -m unittest discover -s tests` runs the visible tests.
