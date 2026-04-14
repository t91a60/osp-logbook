from collections import OrderedDict
from collections.abc import Callable
from threading import Lock
from time import monotonic
from typing import Any

_cache_lock = Lock()
_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_CACHE_MAX_SIZE: int = 1024


def get_or_set[T](key: str, ttl_seconds: int, loader: Callable[[], T]) -> T:
    now = monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry['expires_at'] > now:
            _cache.move_to_end(key)
            return entry['value']

    value = loader()
    with _cache_lock:
        _cache[key] = {
            'value': value,
            'expires_at': monotonic() + max(1, int(ttl_seconds)),
        }
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX_SIZE:
            _cache.popitem(last=False)
    return value


def invalidate_prefix(prefix: str) -> None:
    with _cache_lock:
        keys = [k for k in _cache if k.startswith(prefix)]
        for key in keys:
            _cache.pop(key, None)


def get_vehicles_cached() -> list[dict]:
    """Return all vehicles ordered by name, cached for 300 s."""
    from backend.db import get_db, get_cursor

    def _load() -> list[dict]:
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT * FROM vehicles ORDER BY name')
            return cur.fetchall()
        finally:
            cur.close()

    return get_or_set('vehicles:all', 300, _load)
