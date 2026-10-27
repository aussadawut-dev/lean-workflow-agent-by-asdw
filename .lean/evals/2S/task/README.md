# Task

Rename the function `fetch_usr` to `fetch_user` in `users.py` and update every caller in this repository.
Keep `fetch_usr` working as a deprecated alias: it returns the same result and emits a `DeprecationWarning`
each time it is called. Both names must be listed in `users.__all__`. Do not change behaviour otherwise.
`python3 -m unittest discover -s tests` runs the visible tests.
