"""Comprehensive tests for backend/routes/maintenance.py."""

from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_cursor(fetchone_result=None, fetchall_result=None):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_result
    cur.fetchall.return_value = fetchall_result if fetchall_result is not None else []
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    return cur


def _csrf(client):
    with client.session_transaction() as sess:
        return sess['_csrf_token']


# ---------------------------------------------------------------------------
# Module-level validation helpers
# ---------------------------------------------------------------------------

class TestMaintenanceHelpers:
    def test_require_float_valid(self):
        from backend.routes.maintenance import _require_float
        assert _require_float('9.99', 'Koszt') == pytest.approx(9.99)

    def test_require_float_none(self):
        from backend.routes.maintenance import _require_float
        assert _require_float(None, 'Koszt') is None

    def test_require_float_empty_string(self):
        from backend.routes.maintenance import _require_float
        assert _require_float('', 'Koszt') is None

    def test_require_float_invalid_raises(self):
        from backend.routes.maintenance import _require_float, ValidationError
        with pytest.raises(ValidationError, match='Koszt musi być liczbą'):
            _require_float('bad', 'Koszt')

    def test_require_int_valid(self):
        from backend.routes.maintenance import _require_int
        assert _require_int('12345', 'Stan km') == 12345

    def test_require_int_none(self):
        from backend.routes.maintenance import _require_int
        assert _require_int(None, 'Stan km') is None

    def test_require_int_empty_string(self):
        from backend.routes.maintenance import _require_int
        assert _require_int('', 'Stan km') is None

    def test_require_int_invalid_raises(self):
        from backend.routes.maintenance import _require_int, ValidationError
        with pytest.raises(ValidationError, match='Stan km musi być liczbą całkowitą'):
            _require_int('abc', 'Stan km')

    def test_require_int_zero_raises(self):
        from backend.routes.maintenance import _require_int, ValidationError
        with pytest.raises(ValidationError, match='musi być większy od 0'):
            _require_int('0', 'Stan km')


# ---------------------------------------------------------------------------
# GET /serwis
# ---------------------------------------------------------------------------

class TestMaintenanceGetRoute:
    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_maintenance_get_returns_200(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_get_page, mock_render, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'maint-page'

        response = authenticated_client.get('/serwis')

        assert response.status_code == 200
        assert response.data == b'maint-page'
        mock_render.assert_called_once()
        ctx = mock_render.call_args.kwargs
        assert ctx['selected_status'] == 'all'
        assert ctx['selected_vehicle'] == 'all'

    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_maintenance_get_filter_pending(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_get_page, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'page'

        response = authenticated_client.get('/serwis?status=pending&vehicle_id=2')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['selected_status'] == 'pending'
        assert ctx['selected_vehicle'] == '2'

    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_maintenance_get_filter_overdue(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_get_page, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'page'

        response = authenticated_client.get('/serwis?status=overdue')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['selected_status'] == 'overdue'

    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_maintenance_get_with_date_filters(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_get_page, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'page'

        response = authenticated_client.get('/serwis?od=2024-01-01&do=2024-12-31')
        assert response.status_code == 200

    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_maintenance_get_with_okres_ten(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_get_page, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'page'

        response = authenticated_client.get('/serwis?okres=ten')
        assert response.status_code == 200

    @patch('backend.routes.maintenance.render_template')
    @patch('backend.routes.maintenance.MaintenanceRepository.get_page')
    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_maintenance_get_filter_completed(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_get_page, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'page'

        response = authenticated_client.get('/serwis?status=completed')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['selected_status'] == 'completed'


# ---------------------------------------------------------------------------
# POST /serwis — add maintenance entry
# ---------------------------------------------------------------------------

class TestMaintenancePostRoute:
    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_missing_vehicle_redirects(self, mock_db, mock_cur_fn, mock_vehicles, authenticated_client):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })
        assert response.status_code == 302

    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_active_vehicle')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_invalid_vehicle_redirects(self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_active_v.return_value = None
        mock_vehicles.return_value = []

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '999',
            'date': '2024-05-01',
            'description': 'Przegląd',
        })
        assert response.status_code == 302

    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_active_vehicle')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_invalid_odometer_redirects(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Przegląd',
            'odometer': 'abc',
        })
        assert response.status_code == 302
        mock_cur.execute.assert_not_called()

    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_active_vehicle')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_valid_data_inserts_and_redirects(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Wymiana oleju',
            'odometer': '15000',
            'cost': '250.00',
            'priority': 'high',
            'status': 'pending',
        })
        assert response.status_code == 302
        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_active_vehicle')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_invalid_priority_defaults_to_medium(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = []

        authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Test',
            'priority': 'turbo',
            'status': 'pending',
        })
        # INSERT called — check that priority defaults to 'medium'
        _, call_params = mock_cur.execute.call_args.args
        assert call_params[8] == 'medium'

    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_active_vehicle')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_invalid_status_defaults_to_pending(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = []

        authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Test',
            'priority': 'low',
            'status': 'invalid',
        })
        _, call_params = mock_cur.execute.call_args.args
        assert call_params[7] == 'pending'

    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_active_vehicle')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_integrity_error_raises_validation_error(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        from psycopg2 import IntegrityError
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur.execute.side_effect = IntegrityError('unique violation')
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = []

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Test',
        })
        assert response.status_code == 302
        mock_conn.rollback.assert_called()

    @patch('backend.routes.maintenance.get_vehicles_cached')
    @patch('backend.routes.maintenance.get_active_vehicle')
    @patch('backend.routes.maintenance.get_cursor')
    @patch('backend.routes.maintenance.get_db')
    def test_post_with_due_date(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = []

        response = authenticated_client.post('/serwis', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Przegląd',
            'due_date': '2024-08-01',
        })
        assert response.status_code == 302
        _, call_params = mock_cur.execute.call_args.args
        assert call_params[9] == '2024-08-01'


# ---------------------------------------------------------------------------
# POST /serwis/<eid>/complete
# ---------------------------------------------------------------------------

class TestCompleteMaintenance:
    @patch('backend.routes.maintenance.MaintenanceRepository.complete')
    def test_complete_own_entry(self, mock_complete, authenticated_client):
        mock_complete.return_value = {'id': 1, 'added_by': 'testuser'}

        response = authenticated_client.post('/serwis/1/complete', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 302

    @patch('backend.routes.maintenance.MaintenanceRepository.complete')
    def test_complete_others_entry_forbidden(self, mock_complete, authenticated_client):
        mock_complete.return_value = {'id': 1, 'added_by': 'other_user'}

        response = authenticated_client.post('/serwis/1/complete', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 403

    @patch('backend.routes.maintenance.MaintenanceRepository.complete')
    def test_complete_admin_can_complete_any(self, mock_complete, admin_client):
        mock_complete.return_value = {'id': 5, 'added_by': 'otheruser'}

        response = admin_client.post('/serwis/5/complete', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302

    @patch('backend.routes.maintenance.MaintenanceRepository.complete')
    def test_complete_entry_not_found_redirects(self, mock_complete, authenticated_client):
        mock_complete.return_value = None

        response = authenticated_client.post('/serwis/999/complete', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# POST /serwis/<eid>/next
# ---------------------------------------------------------------------------

class TestCreateNextMaintenance:
    @patch('backend.routes.maintenance.MaintenanceRepository.create_next')
    def test_create_next_entry_not_found(self, mock_create_next, authenticated_client):
        mock_create_next.return_value = None

        response = authenticated_client.post('/serwis/999/next', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 302

    @patch('backend.routes.maintenance.MaintenanceRepository.create_next')
    def test_create_next_entry_forbidden_for_other(self, mock_create_next, authenticated_client):
        mock_create_next.return_value = {
            'added_by': 'otheruser',
            'vehicle_id': 1,
            'odometer': 10000,
            'description': 'Serwis',
            'notes': '',
            'priority': 'medium',
            'due_date': None,
        }

        response = authenticated_client.post('/serwis/1/next', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 403

    @patch('backend.routes.maintenance.MaintenanceRepository.create_next')
    def test_create_next_own_entry_success(self, mock_create_next, authenticated_client):
        mock_create_next.return_value = {
            'added_by': 'testuser',
            'vehicle_id': 1,
            'odometer': 15000,
            'description': 'Wymiana oleju',
            'notes': 'Dobrze',
            'priority': 'high',
            'due_date': '2024-02-01',
        }

        response = authenticated_client.post('/serwis/1/next', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 302

    @patch('backend.routes.maintenance.MaintenanceRepository.create_next')
    def test_create_next_entry_with_invalid_due_date(
        self, mock_create_next, authenticated_client
    ):
        mock_create_next.return_value = {
            'added_by': 'testuser',
            'vehicle_id': 1,
            'odometer': None,
            'description': 'Test',
            'notes': '',
            'priority': 'medium',
            'due_date': 'bad-date',
        }

        response = authenticated_client.post('/serwis/1/next', data={
            '_csrf_token': _csrf(authenticated_client),
        })
        assert response.status_code == 302

    @patch('backend.routes.maintenance.MaintenanceRepository.create_next')
    def test_create_next_admin_success(self, mock_create_next, admin_client):
        mock_create_next.return_value = {
            'added_by': 'someuser',
            'vehicle_id': 2,
            'odometer': 20000,
            'description': 'Przegląd',
            'notes': '',
            'priority': 'low',
            'due_date': None,
        }

        response = admin_client.post('/serwis/3/next', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302
