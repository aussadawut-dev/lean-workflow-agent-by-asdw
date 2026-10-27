# Rate limits

Each user may make at most `limit` requests in any rolling window of `window` seconds: a request at time
`t` is allowed when fewer than `limit` *allowed* requests happened in `(t - window, t]`. Rejected requests do
not count towards the limit.

When a request is rejected, the API answers `429` with `retry_after`: the number of seconds (a float) until
the oldest counted request leaves the window, which is when the next request would be allowed.

Limits are kept per user; one user's traffic never affects another's.
