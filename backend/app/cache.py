"""Tiny in-process TTL cache for query functions.

dbt refreshes the report tables on an hourly schedule, so re-hitting BigQuery
more often than that buys nothing but latency and cost. Each decorated
function gets its own store, keyed by its call args.
"""

import threading
import time
from functools import wraps

from app.config import get_settings


def ttl_cache(fn):
    store: dict[tuple, tuple[float, object]] = {}
    lock = threading.Lock()

    @wraps(fn)
    def wrapper(*args, **kwargs):
        ttl = get_settings().cache_ttl_seconds
        key = (args, tuple(sorted(kwargs.items())))
        now = time.monotonic()

        with lock:
            hit = store.get(key)
            if hit is not None and now - hit[0] < ttl:
                return hit[1]

        result = fn(*args, **kwargs)

        with lock:
            store[key] = (now, result)
        return result

    wrapper.cache_clear = lambda: store.clear()
    return wrapper
