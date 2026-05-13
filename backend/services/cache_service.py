import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, Optional

from backend.infrastructure.cache.redis_cache import RedisCache

# Singleton instancja cache'a na całą aplikację
cache = RedisCache()


def get_or_set[T](key: str, ttl_seconds: int, loader: Callable[[], T], tags: Optional[list[str]] = None) -> T:
    val = cache.get(key)
    if val is not None:
        return val

    val = loader()
    cache.set(key, val, ttl_seconds, tags)
    return val


def invalidate_prefix(prefix: str) -> None:
    """Legacy: usuwa po kluczu. W nowym kodzie używaj invalidate_tags."""
    cache.invalidate_prefix(prefix)


def invalidate_tags(tags: list[str] | str) -> None:
    """Inwaliduje wpisy posiadające wskazane tagi."""
    if isinstance(tags, str):
        tags = [tags]
    cache.invalidate_tags(tags)


def cached(ttl: int, tags: Optional[list[str]] = None, key_prefix: Optional[str] = None):
    """
    Dekorator buforowania.
    Tagi i klucz mogą zawierać nazwy argumentów funkcji,
    np. tags=['report:{vid}'], key_prefix='report:{vid}'.
    Argumenty 'self', 'cls' i 'cur' są ignorowane przy generowaniu klucza.
    """
    def decorator(func):
        sig = inspect.signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Mapowanie przekazanych argumentów do definicji funkcji
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            call_args = bound_args.arguments

            # Jeśli użytkownik podał key_prefix - formatujemy. Inaczej auto.
            if key_prefix:
                formatted_prefix = key_prefix.format(**call_args)
            else:
                formatted_prefix = f"{func.__module__}.{func.__qualname__}"

            # Budowanie pełnego klucza z wartości argumentów
            key_parts = [formatted_prefix]
            for k, v in call_args.items():
                if k not in ('self', 'cls', 'cur'):
                    key_parts.append(f"{k}={v}")
            cache_key = ":".join(key_parts)

            # Formatowanie tagów z wartości argumentów (np. report:{vid} -> report:1)
            formatted_tags = []
            if tags:
                for tag in tags:
                    formatted_tags.append(tag.format(**call_args))

            return get_or_set(
                key=cache_key,
                ttl_seconds=ttl,
                loader=lambda: func(*args, **kwargs),
                tags=formatted_tags
            )

        return wrapper
    return decorator


def get_vehicles_cached() -> list[dict]:
    """Zwraca listę pojazdów, keszowaną na 300 s."""
    from backend.db import get_cursor, get_db

    def _load() -> list[dict]:
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT * FROM vehicles ORDER BY name')
            return cur.fetchall()
        finally:
            cur.close()

    return get_or_set('vehicles:all', 300, _load, tags=['vehicles', 'dashboard'])
