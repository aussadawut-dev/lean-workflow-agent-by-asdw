from limiter import Limiter

BATCH = Limiter(limit=100, window=1)


def run_batch(items, limiter=BATCH):
    done = []
    for item in items:
        if limiter.allow("batch"):
            done.append(item)
    return done
