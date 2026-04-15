"""Tests for backend/helpers.py — paginate() function."""

from unittest.mock import MagicMock
import pytest

from backend.helpers import paginate


def _make_cursor(window_rows, count_row=None):
    """Build a mock cursor that returns window_rows on the first execute
    and optionally count_row on the second (fallback path)."""
    cur = MagicMock()
    fetchall_results = [window_rows]
    fetchone_results = []
    if count_row is not None:
        # Fallback path: first window returns [], then count query, then second window
        fetchall_results = [[], window_rows]
        fetchone_results = [count_row]

    cur.fetchall = MagicMock(side_effect=fetchall_results)
    if fetchone_results:
        cur.fetchone = MagicMock(side_effect=fetchone_results)
    return cur


class TestPaginateBasic:
    """Happy-path pagination."""

    def test_single_page(self):
        rows = [
            {'id': 1, 'name': 'A', '__total_count': 3},
            {'id': 2, 'name': 'B', '__total_count': 3},
            {'id': 3, 'name': 'C', '__total_count': 3},
        ]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()

        entries, total, total_pages, page = paginate(
            conn, cur, 'SELECT COUNT(*)', [], 'SELECT *', [], page=1, page_size=10,
        )
        assert total == 3
        assert total_pages == 1
        assert page == 1
        assert len(entries) == 3
        # __total_count should be stripped from entries
        for e in entries:
            assert '__total_count' not in e

    def test_multi_page_first_page(self):
        rows = [
            {'id': 1, 'val': 'x', '__total_count': 5},
            {'id': 2, 'val': 'y', '__total_count': 5},
        ]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()

        entries, total, total_pages, page = paginate(
            conn, cur, '', [], '', [], page=1, page_size=2,
        )
        assert total == 5
        assert total_pages == 3
        assert page == 1
        assert len(entries) == 2

    def test_multi_page_middle_page(self):
        rows = [
            {'id': 3, 'val': 'z', '__total_count': 10},
            {'id': 4, 'val': 'w', '__total_count': 10},
        ]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()

        entries, total, total_pages, page = paginate(
            conn, cur, '', [], '', [], page=2, page_size=2,
        )
        assert total == 10
        assert total_pages == 5
        assert page == 2


class TestPaginateEdgeCases:
    """Edge cases: empty data, out of range, zero/negative page."""

    def test_empty_result_set(self):
        """Empty result set with zero total rows."""
        cur = MagicMock()
        # First window returns [], then fallback count returns 0, then second window returns []
        cur.fetchall.side_effect = [[], []]
        cur.fetchone.return_value = {'count': 0}
        conn = MagicMock()

        entries, total, total_pages, page = paginate(
            conn, cur, 'SELECT COUNT(*)', [], 'SELECT *', [], page=1, page_size=10,
        )
        assert total == 0
        assert total_pages == 1
        assert page == 1
        assert entries == []

    def test_page_zero_clamped_to_one(self):
        rows = [{'id': 1, '__total_count': 1}]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()

        _, _, _, page = paginate(conn, cur, '', [], '', [], page=0, page_size=10)
        assert page == 1

    def test_negative_page_clamped_to_one(self):
        rows = [{'id': 1, '__total_count': 1}]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()

        _, _, _, page = paginate(conn, cur, '', [], '', [], page=-5, page_size=10)
        assert page == 1

    def test_out_of_range_page_falls_back(self):
        """Page beyond total triggers fallback path and clamps page."""
        cur = MagicMock()
        # First window for page=100 returns [] (no rows)
        # Fallback: count query returns 5 total, second window returns data for clamped page
        fallback_rows = [{'id': 5, '__total_count': 5}]
        cur.fetchall.side_effect = [[], fallback_rows]
        cur.fetchone.return_value = {'count': 5}
        conn = MagicMock()

        entries, total, total_pages, page = paginate(
            conn, cur, 'SELECT COUNT(*)', [], 'SELECT *', [], page=100, page_size=2,
        )
        assert total == 5
        assert total_pages == 3
        assert page == 3  # Clamped to last page

    def test_count_row_tuple_format(self):
        """Fallback count query may return tuple instead of dict."""
        cur = MagicMock()
        cur.fetchall.side_effect = [[], [{'id': 1, '__total_count': 2}]]
        cur.fetchone.return_value = (2,)  # Tuple format
        conn = MagicMock()

        _, total, _, _ = paginate(conn, cur, '', [], '', [], page=999, page_size=10)
        assert total == 2

    def test_page_size_boundary(self):
        """Exactly page_size items means exactly 1 page."""
        rows = [{'id': i, '__total_count': 5} for i in range(5)]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()

        _, total, total_pages, _ = paginate(conn, cur, '', [], '', [], page=1, page_size=5)
        assert total == 5
        assert total_pages == 1

    def test_total_pages_rounds_up(self):
        """6 items with page_size=5 should give 2 total pages."""
        rows = [{'id': i, '__total_count': 6} for i in range(5)]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()

        _, total, total_pages, _ = paginate(conn, cur, '', [], '', [], page=1, page_size=5)
        assert total == 6
        assert total_pages == 2
