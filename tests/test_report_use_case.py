"""
Unit tests for backend/application/report.py

Split into:
  - TestResolvePeriod   — pure function, no mocking needed
  - TestGenerateReportUseCase — DB mocked via get_db / get_cursor
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.application.report import (
    GenerateReportUseCase,
    ReportQuery,
    ReportResult,
    _resolve_period,
)


# ---------------------------------------------------------------------------
# _resolve_period — pure function tests (no mocks)
# ---------------------------------------------------------------------------

class TestResolvePeriod:
    def _today(self):
        return date.today()

    def test_monthly_valid(self):
        canonical, first, last, label = _resolve_period('2026-05', date(2026, 5, 15))
        assert canonical == '2026-05'
        assert first == '2026-05-01'
        assert last == '2026-05-31'
        assert 'maj' in label
        assert '2026' in label

    def test_monthly_december(self):
        _, first, last, _ = _resolve_period('2025-12', date(2025, 12, 1))
        assert first == '2025-12-01'
        assert last == '2025-12-31'

    def test_quarterly_q1(self):
        canonical, first, last, label = _resolve_period('2026-Q1', date(2026, 2, 1))
        assert canonical == '2026-Q1'
        assert first == '2026-01-01'
        assert last == '2026-03-31'
        assert label == 'Q1 2026'

    def test_quarterly_q4(self):
        _, first, last, label = _resolve_period('2025-Q4', date(2025, 11, 1))
        assert first == '2025-10-01'
        assert last == '2025-12-31'
        assert label == 'Q4 2025'

    def test_quarterly_invalid_number_falls_back(self):
        today = date(2026, 5, 1)
        _, first, last, _ = _resolve_period('2026-Q9', today)
        # falls back to current quarter of today
        assert first.startswith('2026')

    def test_invalid_month_falls_back_to_current(self):
        today = date(2026, 5, 15)
        canonical, first, last, _ = _resolve_period('not-a-date', today)
        assert canonical == '2026-05'
        assert first == '2026-05-01'

    def test_empty_string_falls_back_to_current(self):
        today = date(2026, 3, 20)
        canonical, first, last, label = _resolve_period('', today)
        assert canonical == '2026-03'
        assert 'marzec' in label

    def test_monthly_february_non_leap(self):
        _, first, last, _ = _resolve_period('2025-02', date(2025, 2, 1))
        assert last == '2025-02-28'

    def test_monthly_february_leap(self):
        _, first, last, _ = _resolve_period('2024-02', date(2024, 2, 1))
        assert last == '2024-02-29'


# ---------------------------------------------------------------------------
# GenerateReportUseCase — DB mocked
# ---------------------------------------------------------------------------

def _make_cursor(side_effects=None, fetchone_result=None):
    cur = MagicMock()
    if side_effects is not None:
        cur.fetchall.side_effect = side_effects
    else:
        cur.fetchall.return_value = []
    cur.fetchone.return_value = fetchone_result or {'total_km': 0}
    return cur


class TestGenerateReportUseCase:
    @patch('backend.application.report.get_cursor')
    @patch('backend.application.report.get_db')
    def test_returns_report_result(self, mock_db, mock_cur_fn):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(side_effects=[[], [], [], []])
        mock_cur_fn.return_value = mock_cur

        query = ReportQuery(month_str='2026-05', vehicle_id=None)
        result = GenerateReportUseCase.execute(query, vehicles=[])

        assert isinstance(result, ReportResult)
        assert result.trip_entries == []
        assert result.total_km == 0
        assert 'maj' in result.period_label
        assert result.selected_vehicle == ''
        mock_cur.close.assert_called_once()

    @patch('backend.application.report.get_cursor')
    @patch('backend.application.report.get_db')
    def test_vehicle_filter_sets_selected_vehicle(self, mock_db, mock_cur_fn):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(side_effects=[[], [], [], []])
        mock_cur_fn.return_value = mock_cur

        vehicles = [{'id': 3, 'name': 'SLR', 'plate': 'KR003'}]
        query = ReportQuery(month_str='2026-05', vehicle_id=3)
        result = GenerateReportUseCase.execute(query, vehicles=vehicles)

        assert result.selected_vehicle == '3'
        assert result.report_vehicle == vehicles[0]

    @patch('backend.application.report.get_cursor')
    @patch('backend.application.report.get_db')
    def test_fuel_and_maint_indexed_by_vehicle_id(self, mock_db, mock_cur_fn):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(side_effects=[
            [],   # trip_entries
            [],   # trip_summary
            [{'vehicle_id': 7, 'total_liters': 40.0, 'total_cost': 200.0}],
            [{'vehicle_id': 7, 'total_cost': 80.0}],
        ])
        mock_cur_fn.return_value = mock_cur

        result = GenerateReportUseCase.execute(ReportQuery(), vehicles=[])

        assert 7 in result.fuel_by_vid
        assert result.fuel_by_vid[7]['total_liters'] == 40.0
        assert 7 in result.maint_by_vid

    @patch('backend.application.report.get_cursor')
    @patch('backend.application.report.get_db')
    def test_closes_cursor_on_exception(self, mock_db, mock_cur_fn):
        mock_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur_fn.return_value = mock_cur
        mock_cur.execute.side_effect = RuntimeError('db boom')

        with pytest.raises(RuntimeError):
            GenerateReportUseCase.execute(ReportQuery(), vehicles=[])

        mock_cur.close.assert_called_once()

    @patch('backend.application.report.get_cursor')
    @patch('backend.application.report.get_db')
    def test_invalid_period_falls_back_to_current_month(self, mock_db, mock_cur_fn):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(side_effects=[[], [], [], []])
        mock_cur_fn.return_value = mock_cur

        result = GenerateReportUseCase.execute(
            ReportQuery(month_str='garbage'), vehicles=[]
        )

        # month_str should be a valid YYYY-MM string for current month
        today = date.today()
        assert result.month_str == today.strftime('%Y-%m')

    @patch('backend.application.report.get_cursor')
    @patch('backend.application.report.get_db')
    def test_executes_five_queries(self, mock_db, mock_cur_fn):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(side_effects=[[], [], [], []])
        mock_cur_fn.return_value = mock_cur

        GenerateReportUseCase.execute(ReportQuery(), vehicles=[])

        # trip_entries, total_km (fetchone), trip_summary, fuel, maintenance
        assert mock_cur.execute.call_count == 5
