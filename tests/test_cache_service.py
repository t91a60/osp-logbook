"""Tests for backend/services/cache_service.py."""
import threading

import pytest

pytest.importorskip("redis")

from backend.services import cache_service


@pytest.fixture(autouse=True)
def _clear_cache():
    cache_service.cache.clear()
    yield
    cache_service.cache.clear()


class TestGetOrSet:
    def test_caches_value(self):
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return "result"

        assert cache_service.get_or_set("key1", 60, loader) == "result"
        assert cache_service.get_or_set("key1", 60, loader) == "result"
        assert call_count == 1

    def test_different_keys_independent(self):
        cache_service.get_or_set("a", 60, lambda: "alpha")
        cache_service.get_or_set("b", 60, lambda: "beta")
        assert cache_service.get_or_set("a", 60, lambda: "WRONG") == "alpha"
        assert cache_service.get_or_set("b", 60, lambda: "WRONG") == "beta"

    def test_none_value_is_cached(self):
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return None

        assert cache_service.get_or_set("n", 60, loader) is None
        assert cache_service.get_or_set("n", 60, loader) is None
        assert call_count == 1

    def test_ttl_floor_is_one_second(self):
        cache_service.get_or_set("z", 1, lambda: "val")
        fetched = cache_service.cache.get("z")
        assert fetched is not None


class TestInvalidatePrefix:
    def test_removes_matching_keys(self):
        cache_service.get_or_set("api:km:1", 60, lambda: 100)
        cache_service.get_or_set("api:km:2", 60, lambda: 200)
        cache_service.get_or_set("other:key", 60, lambda: "keep")

        cache_service.invalidate_prefix("api:km:")

        call_count = 0

        def counter():
            nonlocal call_count
            call_count += 1
            return "new"

        cache_service.get_or_set("api:km:1", 60, counter)
        assert call_count == 1
        assert cache_service.get_or_set("other:key", 60, lambda: "WRONG") == "keep"

    def test_invalidate_nonexistent_prefix_is_noop(self):
        cache_service.get_or_set("foo", 60, lambda: "bar")
        cache_service.invalidate_prefix("nonexistent:")
        assert cache_service.get_or_set("foo", 60, lambda: "WRONG") == "bar"

    def test_empty_prefix_clears_all(self):
        cache_service.get_or_set("a", 60, lambda: 1)
        cache_service.get_or_set("b", 60, lambda: 2)
        cache_service.invalidate_prefix("")
        assert cache_service.cache.get("a") is None
        assert cache_service.cache.get("b") is None


class TestThreadSafety:
    def test_concurrent_access(self):
        errors = []
        counter = {"value": 0}
        lock = threading.Lock()

        def loader():
            with lock:
                counter["value"] += 1
            time.sleep(0.001)
            return counter["value"]

        def worker(key):
            try:
                for _ in range(50):
                    cache_service.get_or_set(key, 60, loader)
            except Exception:  # pragma: no cover - safety net
                errors.append("err")

        threads = [threading.Thread(target=worker, args=(f"k{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
