"""Comprehensive tests for backend/routes/report.py route behavior."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch


def _make_cursor(fetchone_result=None, fetchall_result=None, side_effects=None):
    cur = MagicMock()
    if side_effects is not None:
        cur.fetchall.side_effect = side_effects
    else:
        cur.fetchall.return_value = fetchall_result if fetchall_result is not None else []
    cur.fetchone.return_value = fetchone_result
    return cur


class TestReportRoute:
    """Tests for GET /raport."""

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_vehicles_cached')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_get_renders_template(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(
            fetchone_result={'total_km': 0},
            side_effects=[[], [], [], []],
        )
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA', 'plate': 'KR1'}]
        mock_render.return_value = 'report-page'

        response = authenticated_client.get('/raport')

        assert response.status_code == 200
        assert response.data == b'report-page'
        mock_render.assert_called_once()
        ctx = mock_render.call_args.kwargs
        assert 'vehicles' in ctx
        assert 'trip_entries' in ctx
        assert 'total_km' in ctx

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_vehicles_cached')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_get_with_vehicle_filter(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(
            fetchone_result={'total_km': 120},
            side_effects=[
                [{'id': 1, 'date': date.today(), 'driver': 'Jan', 'purpose': 'Pożar',
                  'odo_start': 1000, 'odo_end': 1120, 'time_start': None,
                  'time_end': None, 'notes': '', 'created_at': None, 'vname': 'GBA'}],
                [{'vehicle_id': 1, 'trip_count': 1, 'total_km': 120, 'name': 'GBA', 'plate': 'KR1'}],
                [{'vehicle_id': 1, 'total_liters': 30.0, 'total_cost': 180.0}],
                [{'vehicle_id': 1, 'total_cost': 50.0}],
            ],
        )
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA', 'plate': 'KR1'}]
        mock_render.return_value = 'report-page'

        today_str = date.today().strftime('%Y-%m')
        response = authenticated_client.get(f'/raport?month={today_str}&vehicle_id=1')

        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['selected_vehicle'] == '1'

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_vehicles_cached')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_get_invalid_month_falls_back_to_current(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(
            fetchone_result={'total_km': 0},
            side_effects=[[], [], [], []],
        )
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = []
        mock_render.return_value = 'page'

        response = authenticated_client.get('/raport?month=invalid-date')

        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        expected_month = date.today().strftime('%Y-%m')
        assert ctx['month_str'] == expected_month

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_vehicles_cached')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_get_fuel_and_maint_summary_mapped_to_vehicle(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(
            fetchone_result={'total_km': 50},
            side_effects=[
                [],  # trip_entries
                [{'vehicle_id': 2, 'trip_count': 2, 'total_km': 50, 'name': 'GBA', 'plate': 'KR1', 'id': 2}],
                [{'vehicle_id': 2, 'total_liters': 60.0, 'total_cost': 360.0}],
                [{'vehicle_id': 2, 'total_cost': 100.0}],
            ],
        )
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = [{'id': 2, 'name': 'GBA', 'plate': 'KR1'}]
        mock_render.return_value = 'page'

        response = authenticated_client.get('/raport')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert 2 in ctx['fuel_by_vid']
        assert 2 in ctx['maint_by_vid']

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_vehicles_cached')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_cursor_closed_on_return(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(
            fetchone_result={'total_km': 0},
            side_effects=[[], [], [], []],
        )
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = []
        mock_render.return_value = 'page'

        authenticated_client.get('/raport')
        mock_cur.close.assert_called_once()


class TestReportPrintRoute:
    """Tests for GET /report/print/<vehicle_id>/<period>."""

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_print_monthly_renders(
        self, mock_db, mock_cur_fn, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        vehicle_row = {'id': 1, 'name': 'GBA', 'plate': 'KR001', 'type': 'gaśniczy'}
        trip_rows = [
            {'date': date(2024, 5, 10), 'driver': 'Jan K.', 'purpose': 'Pożar', 'odo_start': 100, 'odo_end': 120, 'notes': ''},
            {'date': date(2024, 5, 15), 'driver': 'Ewa N.', 'purpose': 'Ćwiczenia', 'odo_start': None, 'odo_end': None, 'notes': 'brak km'},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [vehicle_row, {'km': 50}]
        mock_cur.fetchall.return_value = trip_rows
        mock_cur_fn.return_value = mock_cur
        mock_render.return_value = 'print-page'

        response = authenticated_client.get('/report/print/1/2024-05')

        assert response.status_code == 200
        assert response.data == b'print-page'
        ctx = mock_render.call_args.kwargs
        assert ctx['vehicle'] == vehicle_row
        assert ctx['folio_sum'] == 20   # 120 - 100
        assert ctx['carry_over'] == 50
        assert ctx['period_total'] == 70   # 50 + 20
        assert len(ctx['rows']) == 2

    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_print_vehicle_not_found_returns_404(
        self, mock_db, mock_cur_fn, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_cur_fn.return_value = mock_cur

        response = authenticated_client.get('/report/print/9999/2024-05')
        assert response.status_code == 404

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_print_quarterly_period(
        self, mock_db, mock_cur_fn, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        vehicle_row = {'id': 2, 'name': 'SLR', 'plate': 'KR002', 'type': 'ratowniczy'}
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [vehicle_row, {'km': None}]
        mock_cur.fetchall.return_value = []
        mock_cur_fn.return_value = mock_cur
        mock_render.return_value = 'print-q-page'

        response = authenticated_client.get('/report/print/2/2024-Q1')

        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['period_label'] == 'Q1 2024'
        assert ctx['carry_over'] == 0
        assert ctx['folio_sum'] == 0

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_print_row_with_missing_odo_has_empty_km(
        self, mock_db, mock_cur_fn, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        vehicle_row = {'id': 1, 'name': 'GBA', 'plate': 'KR001', 'type': ''}
        trip_rows = [
            {'date': date(2024, 3, 5), 'driver': 'Marek', 'purpose': 'Alarm', 'odo_start': None, 'odo_end': None, 'notes': ''},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [vehicle_row, {'km': 0}]
        mock_cur.fetchall.return_value = trip_rows
        mock_cur_fn.return_value = mock_cur
        mock_render.return_value = 'p'

        authenticated_client.get('/report/print/1/2024-03')
        ctx = mock_render.call_args.kwargs
        row = ctx['rows'][0]
        assert row['trip_km'] == ''
        assert row['odo_start'] == ''
        assert row['odo_end'] == ''

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_print_carry_over_null_treated_as_zero(
        self, mock_db, mock_cur_fn, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        vehicle_row = {'id': 1, 'name': 'GBA', 'plate': '', 'type': ''}
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [vehicle_row, {'km': None}]
        mock_cur.fetchall.return_value = []
        mock_cur_fn.return_value = mock_cur
        mock_render.return_value = 'p'

        authenticated_client.get('/report/print/1/2024-01')
        ctx = mock_render.call_args.kwargs
        assert ctx['carry_over'] == 0

    def test_report_print_requires_login(self, client):
        response = client.get('/report/print/1/2024-05')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    def test_report_requires_login(self, client):
        response = client.get('/raport')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    @patch('backend.routes.report.render_template')
    @patch('backend.routes.report.get_vehicles_cached')
    @patch('backend.routes.report.get_cursor')
    @patch('backend.routes.report.get_db')
    def test_report_empty_state_shows_no_trips(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchone_result={'total_km': 0}, side_effects=[[], [], [], []])
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = []
        mock_render.return_value = 'page'

        response = authenticated_client.get('/raport')

        assert response.status_code == 200
        assert mock_render.call_args.kwargs['trip_entries'] == []
        assert mock_render.call_args.kwargs['report_vehicle'] is None
