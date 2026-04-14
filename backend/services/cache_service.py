from threading import Lock
from time import monotonic
from typing import Any, Callable

_cache_lock = Lock()
_cache: dict[str, dict[str, Any]] = {}


def get_or_set(key: str, ttl_seconds: int, loader: Callable[[], Any]) -> Any:
    now = monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry['expires_at'] > now:
            return entry['value']

    value = loader()
    with _cache_lock:
        _cache[key] = {
            'value': value,
            'expires_at': monotonic() + max(1, int(ttl_seconds)),
        }
    return value


def invalidate_prefix(prefix: str) -> None:
    with _cache_lock:
        keys = [k for k in _cache.keys() if k.startswith(prefix)]
        for key in keys:
            _cache.pop(key, None)
