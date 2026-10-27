from limiter import Limiter

LIMITER = Limiter(limit=3, window=60)


def handle(user, limiter=LIMITER):
    decision = limiter.check(user)
    if not decision.allowed:
        return 429, {"retry_after": decision.retry_after}
    return 200, {"ok": True}
