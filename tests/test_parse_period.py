"""Tests for backend/routes/report.py — _parse_period helper."""

from datetime import date, timedelta

from backend.routes.report import _parse_period


class TestParsePeriodQuarterly:
    """Period strings with -Q notation (quarterly)."""

    def test_q1(self):
        first, last, label = _parse_period('2024-Q1')
        assert first == date(2024, 1, 1)
        assert last == date(2024, 3, 31)
        assert label == 'Q1 2024'

    def test_q2(self):
        first, last, label = _parse_period('2024-Q2')
        assert first == date(2024, 4, 1)
        assert last == date(2024, 6, 30)
        assert label == 'Q2 2024'

    def test_q3(self):
        first, last, label = _parse_period('2024-Q3')
        assert first == date(2024, 7, 1)
        assert last == date(2024, 9, 30)
        assert label == 'Q3 2024'

    def test_q4(self):
        first, last, label = _parse_period('2024-Q4')
        assert first == date(2024, 10, 1)
        assert last == date(2024, 12, 31)
        assert label == 'Q4 2024'

    def test_q4_spanning_year_boundary(self):
        """Q4 last_day should be Dec 31 of the same year."""
        first, last, _ = _parse_period('2025-Q4')
        assert first == date(2025, 10, 1)
        assert last == date(2025, 12, 31)

    def test_invalid_quarter_number_falls_back(self):
        """Invalid quarter number (e.g., Q5) falls back to current quarter."""
        today = date.today()
        first, last, label = _parse_period('2024-Q5')
        expected_quarter = (today.month - 1) // 3 + 1
        assert f'Q{expected_quarter}' in label

    def test_invalid_year_in_quarter_falls_back(self):
        """Non-numeric year in quarterly format falls back to current quarter."""
        today = date.today()
        first, last, label = _parse_period('abc-Q1')
        expected_quarter = (today.month - 1) // 3 + 1
        assert f'Q{expected_quarter}' in label


class TestParsePeriodMonthly:
    """Period strings in YYYY-MM format (monthly)."""

    def test_january(self):
        first, last, label = _parse_period('2024-01')
        assert first == date(2024, 1, 1)
        assert last == date(2024, 1, 31)
        assert label == '2024-01'

    def test_february_non_leap(self):
        first, last, _ = _parse_period('2023-02')
        assert first == date(2023, 2, 1)
        assert last == date(2023, 2, 28)

    def test_february_leap_year(self):
        first, last, _ = _parse_period('2024-02')
        assert first == date(2024, 2, 1)
        assert last == date(2024, 2, 29)

    def test_december(self):
        """December should end on Dec 31."""
        first, last, _ = _parse_period('2024-12')
        assert first == date(2024, 12, 1)
        assert last == date(2024, 12, 31)

    def test_month_with_30_days(self):
        first, last, _ = _parse_period('2024-04')
        assert first == date(2024, 4, 1)
        assert last == date(2024, 4, 30)


class TestParsePeriodInvalid:
    """Invalid period strings should fall back to current month."""

    def test_empty_string(self):
        today = date.today()
        first, last, label = _parse_period('')
        assert first == today.replace(day=1)
        assert label == today.strftime('%Y-%m')

    def test_garbage_string(self):
        today = date.today()
        first, last, label = _parse_period('not-a-date')
        assert first == today.replace(day=1)

    def test_partial_date(self):
        today = date.today()
        first, last, label = _parse_period('2024')
        assert first == today.replace(day=1)

    def test_invalid_month_13(self):
        """Month 13 is invalid, should fall back."""
        today = date.today()
        first, last, label = _parse_period('2024-13')
        assert first == today.replace(day=1)

    def test_invalid_month_00(self):
        """Month 00 is invalid, should fall back."""
        today = date.today()
        first, last, label = _parse_period('2024-00')
        assert first == today.replace(day=1)
