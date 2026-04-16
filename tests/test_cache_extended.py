"""Tests for cache_service — get_vehicles_cached, FIFO eviction, and edge cases."""

from unittest.mock import patch
from backend.services import cache_service


class TestGetVehiclesCached:
    """Test the get_vehicles_cached wrapper function."""

    @patch('backend.services.cache_service.get_or_set')
    def test_calls_get_or_set_with_correct_key(self, mock_get_or_set):
        mock_get_or_set.return_value = [{'id': 1, 'name': 'Fiat Ducato'}]
        result = cache_service.get_vehicles_cached()
        mock_get_or_set.assert_called_once()
        call_args = mock_get_or_set.call_args
        assert call_args[0][0] == 'vehicles:all'
        assert call_args[0][1] == 300
        assert result == [{'id': 1, 'name': 'Fiat Ducato'}]

    @patch('backend.services.cache_service.get_or_set')
    def test_returns_empty_list_when_no_vehicles(self, mock_get_or_set):
        mock_get_or_set.return_value = []
        result = cache_service.get_vehicles_cached()
        assert result == []


class TestCacheFIFOEviction:
    """Test that cache evicts oldest entries when exceeding _CACHE_MAX_SIZE."""

    def setup_method(self):
        cache_service._cache.clear()

    def teardown_method(self):
        cache_service._cache.clear()

    def test_evicts_oldest_when_full(self):
        """When cache exceeds max size, oldest entries are evicted."""
        original_max = cache_service._CACHE_MAX_SIZE
        try:
            # Temporarily reduce max size for testing
            cache_service._CACHE_MAX_SIZE = 5
            for i in range(7):
                cache_service.get_or_set(f'key{i}', 60, lambda i=i: f'val{i}')

            # Should have at most 5 entries
            assert len(cache_service._cache) <= 5
            # Oldest keys (key0, key1) should be evicted
            assert 'key0' not in cache_service._cache
            assert 'key1' not in cache_service._cache
            # Newest keys should be present
            assert 'key6' in cache_service._cache
            assert 'key5' in cache_service._cache
        finally:
            cache_service._CACHE_MAX_SIZE = original_max


class TestCacheGetOrSetEdgeCases:
    """Additional edge cases for get_or_set."""

    def setup_method(self):
        cache_service._cache.clear()

    def teardown_method(self):
        cache_service._cache.clear()

    def test_loader_exception_propagates(self):
        """If loader raises, exception propagates to caller."""
        import pytest

        def bad_loader():
            raise RuntimeError('DB down')

        with pytest.raises(RuntimeError, match='DB down'):
            cache_service.get_or_set('failing', 60, bad_loader)

    def test_negative_ttl_treated_as_one_second(self):
        """Negative TTL uses max(1, ...) = 1 second."""
        cache_service.get_or_set('neg_ttl', -10, lambda: 'val')
        entry = cache_service._cache.get('neg_ttl')
        assert entry is not None

    def test_move_to_end_on_hit(self):
        """Accessing a cached key moves it to the end (LRU-like)."""
        cache_service.get_or_set('first', 60, lambda: 'a')
        cache_service.get_or_set('second', 60, lambda: 'b')
        cache_service.get_or_set('third', 60, lambda: 'c')

        # Access 'first' to move it to end
        cache_service.get_or_set('first', 60, lambda: 'WRONG')

        keys = list(cache_service._cache.keys())
        assert keys[-1] == 'first'

    def test_zero_value_cached(self):
        """Falsy values like 0 are cached (not treated as missing)."""
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return 0

        assert cache_service.get_or_set('zero', 60, loader) == 0
        assert cache_service.get_or_set('zero', 60, loader) == 0
        assert call_count == 1

    def test_false_value_cached(self):
        """Boolean False is cached."""
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return False

        assert cache_service.get_or_set('false', 60, loader) is False
        assert cache_service.get_or_set('false', 60, loader) is False
        assert call_count == 1

    def test_empty_string_value_cached(self):
        """Empty string is cached."""
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return ''

        assert cache_service.get_or_set('empty', 60, loader) == ''
        assert cache_service.get_or_set('empty', 60, loader) == ''
        assert call_count == 1
