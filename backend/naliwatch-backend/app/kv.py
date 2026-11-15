from datetime import date

import redis

from .config import settings

r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
rb = redis.Redis.from_url(settings.redis_url, decode_responses=False)  # binary (media in bot flow)


def rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """True if the call is allowed."""
    n = r.incr(key)
    if n == 1:
        r.expire(key, window_seconds)
    return n <= limit


def daily_counter_ok(name: str, cap: int) -> bool:
    key = f"daily:{name}:{date.today().isoformat()}"
    n = r.incr(key)
    if n == 1:
        r.expire(key, 172800)
    return n <= cap
