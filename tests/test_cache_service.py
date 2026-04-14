"""Tests for backend/services/cache_service.py — thread-safe TTL cache."""

import time
import threading
import pytest

from backend.services import cache_service


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure the global cache is empty before and after each test."""
    cache_service._cache.clear()
    yield
    cache_service._cache.clear()


class TestGetOrSet:
    def test_caches_value(self):
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return 'result'

        assert cache_service.get_or_set('key1', 60, loader) == 'result'
        assert cache_service.get_or_set('key1', 60, loader) == 'result'
        assert call_count == 1  # loader called only once

    def test_different_keys_independent(self):
        cache_service.get_or_set('a', 60, lambda: 'alpha')
        cache_service.get_or_set('b', 60, lambda: 'beta')
        assert cache_service.get_or_set('a', 60, lambda: 'WRONG') == 'alpha'
        assert cache_service.get_or_set('b', 60, lambda: 'WRONG') == 'beta'

    def test_expired_entry_refreshed(self):
        cache_service.get_or_set('x', 1, lambda: 'old')
        # Manually expire the entry
        cache_service._cache['x']['expires_at'] = 0
        result = cache_service.get_or_set('x', 60, lambda: 'new')
        assert result == 'new'

    def test_none_value_is_cached(self):
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return None

        assert cache_service.get_or_set('n', 60, loader) is None
        assert cache_service.get_or_set('n', 60, loader) is None
        assert call_count == 1

    def test_ttl_floor_is_one_second(self):
        """TTL uses max(1, int(ttl_seconds)), so 0 becomes 1."""
        cache_service.get_or_set('z', 0, lambda: 'val')
        entry = cache_service._cache.get('z')
        assert entry is not None
        # The expiry should be at least 1 second from now
        assert entry['expires_at'] > time.monotonic()


class TestInvalidatePrefix:
    def test_removes_matching_keys(self):
        cache_service.get_or_set('api:km:1', 60, lambda: 100)
        cache_service.get_or_set('api:km:2', 60, lambda: 200)
        cache_service.get_or_set('other:key', 60, lambda: 'keep')

        cache_service.invalidate_prefix('api:km:')

        # Matching keys removed — loader is called again
        call_count = 0

        def counter():
            nonlocal call_count
            call_count += 1
            return 'new'

        cache_service.get_or_set('api:km:1', 60, counter)
        assert call_count == 1  # loader was called = key was invalidated

        # Non-matching key still cached
        assert cache_service.get_or_set('other:key', 60, lambda: 'WRONG') == 'keep'

    def test_invalidate_nonexistent_prefix_is_noop(self):
        cache_service.get_or_set('foo', 60, lambda: 'bar')
        cache_service.invalidate_prefix('nonexistent:')
        assert cache_service.get_or_set('foo', 60, lambda: 'WRONG') == 'bar'

    def test_empty_prefix_clears_all(self):
        cache_service.get_or_set('a', 60, lambda: 1)
        cache_service.get_or_set('b', 60, lambda: 2)
        cache_service.invalidate_prefix('')  # Every key starts with ''
        assert cache_service._cache == {}


class TestThreadSafety:
    def test_concurrent_access(self):
        """Multiple threads can read/write without errors."""
        errors = []
        counter = {'value': 0}
        lock = threading.Lock()

        def loader():
            with lock:
                counter['value'] += 1
            time.sleep(0.001)
            return counter['value']

        def worker(key):
            try:
                for _ in range(50):
                    cache_service.get_or_set(key, 60, loader)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f'k{i}',)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
