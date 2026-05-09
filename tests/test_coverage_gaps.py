"""Additional tests to fill gaps in equipment, fuel, trips, api, and app coverage."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest


def _csrf(client):
    with client.session_transaction() as sess:
        return sess['_csrf_token']


def _make_cursor(fetchone=None, fetchall=None):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    return cur


# ---------------------------------------------------------------------------
# Equipment — edit, delete, preload, and API endpoint
# ---------------------------------------------------------------------------

class TestEquipmentEditRoute:
    @patch('backend.routes.equipment.render_template')
    @patch('backend.routes.equipment.get_vehicles_cached')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_edit_get_renders_form(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, admin_client
    ):
        mock_db.return_value = MagicMock()
        item = {'id': 5, 'name': 'Siekiera', 'quantity': 1, 'unit': 'szt',
                'category': 'Pozostałe', 'notes': '', 'vehicle_id': 2, 'vname': 'GBA'}
        mock_cur = _make_cursor(fetchone=item)
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = [{'id': 2, 'name': 'GBA'}]
        mock_render.return_value = 'edit-form'

        response = admin_client.get('/sprzet/5/edytuj')
        assert response.status_code == 200
        assert response.data == b'edit-form'
        assert mock_render.call_args.args[0] == 'equipment_edit.html'

    @patch('backend.routes.equipment.render_template')
    @patch('backend.routes.equipment.get_vehicles_cached')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_edit_get_not_found_redirects(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_render, admin_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchone=None)
        mock_cur_fn.return_value = mock_cur
        mock_vehicles.return_value = []
        mock_render.return_value = 'edit-form'

        response = admin_client.get('/sprzet/999/edytuj')
        assert response.status_code == 302

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_edit_post_updates_and_redirects(
        self, mock_db, mock_cur_fn, mock_audit, admin_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        item = {'id': 5, 'name': 'Siekiera', 'quantity': 1, 'unit': 'szt',
                'category': 'Pozostałe', 'notes': '', 'vehicle_id': 2, 'vname': 'GBA'}
        mock_cur = _make_cursor(fetchone=item)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/5/edytuj', data={
            '_csrf_token': _csrf(admin_client),
            'name': 'Siekiera bojowa',
            'quantity': '2',
            'unit': 'szt',
            'category': 'Pozostałe',
            'notes': '',
        })
        assert response.status_code == 302
        assert '/sprzet' in response.headers['Location']
        mock_conn.commit.assert_called_once()
        mock_audit.log.assert_called_once_with('Edycja', 'Sprzęt', 'ID: 5, Nazwa: Siekiera bojowa')

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_edit_post_invalid_category_defaults(
        self, mock_db, mock_cur_fn, mock_audit, admin_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        item = {'id': 3, 'name': 'Sprzęt', 'quantity': 1, 'unit': 'szt',
                'category': 'Pozostałe', 'notes': '', 'vehicle_id': 1, 'vname': 'GBA'}
        mock_cur = _make_cursor(fetchone=item)
        mock_cur_fn.return_value = mock_cur

        admin_client.post('/sprzet/3/edytuj', data={
            '_csrf_token': _csrf(admin_client),
            'name': 'Sprzęt nowy',
            'quantity': 'abc',   # invalid — defaults to 1
            'unit': 'szt',
            'category': 'Nieistniejąca kategoria',  # invalid — defaults to Pozostałe
            'notes': '',
        })
        _, call_params = mock_cur.execute.call_args.args
        # category is 4th param (index 3 in the UPDATE call)
        assert call_params[3] == 'Pozostałe'
        assert call_params[1] == 1   # quantity defaulted to 1


class TestEquipmentDeleteRoute:
    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_delete_success(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        item = {'vehicle_id': 3, 'name': 'Defibrylator'}
        mock_cur = _make_cursor(fetchone=item)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/7/usun', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302
        mock_conn.commit.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_delete_not_found_redirects(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchone=None)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/999/usun', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302


class TestEquipmentPreloadRoute:
    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_preload_success(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor(fetchone={'id': 1}, fetchall=[])
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/1/preload', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302
        mock_conn.commit.assert_called_once()
        mock_audit.log.assert_called_once()
        assert 'Ducato' in mock_audit.log.call_args.args[2]

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_preload_vehicle_not_found_redirects(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchone=None)
        mock_cur_fn.return_value = mock_cur

        response = admin_client.post('/sprzet/999/preload', data={
            '_csrf_token': _csrf(admin_client),
        })
        assert response.status_code == 302

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_preload_skips_existing(self, mock_db, mock_cur_fn, mock_audit, admin_client):
        """Items already in DB by name should not be inserted again."""
        from backend.routes.equipment import DUCATO_EQUIPMENT
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn

        # Simulate all Ducato items already existing
        all_names = [{'name': item[0]} for item in DUCATO_EQUIPMENT]
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {'id': 1}
        mock_cur.fetchall.return_value = all_names
        mock_cur_fn.return_value = mock_cur

        admin_client.post('/sprzet/1/preload', data={'_csrf_token': _csrf(admin_client)})
        # executemany should NOT be called since all items already exist
        mock_cur.executemany.assert_not_called()


class TestEquipmentApiEndpoint:
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_api_vehicle_equipment_returns_json_list(
        self, mock_db, mock_cur_fn, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        items = [
            {'id': 1, 'name': 'Siekiera', 'quantity': 1, 'unit': 'szt', 'category': 'Pozostałe'},
            {'id': 2, 'name': 'Piła', 'quantity': 1, 'unit': 'szt', 'category': 'Pilarstwo'},
        ]
        mock_cur = _make_cursor(fetchall=items)
        mock_cur_fn.return_value = mock_cur

        response = authenticated_client.get('/api/vehicle/3/equipment')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]['name'] == 'Siekiera'

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_api_vehicle_equipment_empty_returns_empty_list(
        self, mock_db, mock_cur_fn, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur = _make_cursor(fetchall=[])
        mock_cur_fn.return_value = mock_cur

        response = authenticated_client.get('/api/vehicle/99/equipment')
        assert response.status_code == 200
        assert response.get_json() == []

    def test_api_vehicle_equipment_requires_login(self, client):
        response = client.get('/api/vehicle/1/equipment')
        assert response.status_code == 302


class TestEquipmentAddEdgeCases:
    """Cover missing branches in equipment_add."""

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_add_missing_name_redirects(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()

        response = admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '1',
            'name': '',   # empty name
        })
        assert response.status_code == 302

    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_add_missing_vehicle_redirects(self, mock_db, mock_cur_fn, admin_client):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()

        response = admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '',
            'name': 'Test sprzęt',
        })
        assert response.status_code == 302

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_add_invalid_category_defaults_to_pozostale(
        self, mock_db, mock_cur_fn, mock_audit, admin_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur

        admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '1',
            'name': 'Sprzęt testowy',
            'category': 'Nieistniejąca kategoria',
            'quantity': '1',
        })
        _, params = mock_cur.execute.call_args.args
        assert params[4] == 'Pozostałe'

    @patch('backend.routes.equipment.AuditService')
    @patch('backend.routes.equipment.get_cursor')
    @patch('backend.routes.equipment.get_db')
    def test_equipment_add_invalid_quantity_defaults_to_one(
        self, mock_db, mock_cur_fn, mock_audit, admin_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur

        admin_client.post('/sprzet/dodaj', data={
            '_csrf_token': _csrf(admin_client),
            'vehicle_id': '2',
            'name': 'Sprzęt',
            'category': 'Pozostałe',
            'quantity': 'abc',  # invalid
        })
        _, params = mock_cur.execute.call_args.args
        assert params[2] == 1  # quantity defaults to 1


# ---------------------------------------------------------------------------
# Fuel route — additional coverage
# ---------------------------------------------------------------------------

class TestFuelRouteAdditional:
    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_active_vehicle')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_post_empty_vehicle_id_redirects(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []

        response = authenticated_client.post('/tankowania', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '',
            'date': '2024-05-01',
            'driver': 'Jan',
            'liters': '10',
        })
        assert response.status_code == 302
        mock_active_v.assert_not_called()

    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_active_vehicle')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_post_invalid_vehicle_redirects(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_active_v.return_value = None  # vehicle not found

        response = authenticated_client.post('/tankowania', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '999',
            'date': '2024-05-01',
            'driver': 'Jan',
            'liters': '10',
        })
        assert response.status_code == 302

    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_active_vehicle')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_post_valid_data_commits(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]

        response = authenticated_client.post('/tankowania', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'driver': 'Jan Kowalski',
            'liters': '40.5',
            'cost': '220.00',
            'odometer': '15000',
        })
        assert response.status_code == 302
        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_active_vehicle')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_post_integrity_error_rollback(
        self, mock_db, mock_cur_fn, mock_active_v, mock_vehicles, authenticated_client
    ):
        from psycopg2 import IntegrityError
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor()
        mock_cur.execute.side_effect = IntegrityError('constraint')
        mock_cur_fn.return_value = mock_cur
        mock_active_v.return_value = {'id': 1}
        mock_vehicles.return_value = []

        response = authenticated_client.post('/tankowania', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'driver': 'Jan',
            'liters': '30',
        })
        assert response.status_code == 302
        mock_conn.rollback.assert_called()

    @patch('backend.routes.fuel.render_template')
    @patch('backend.routes.fuel.paginate')
    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_get_with_add_param(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_paginate, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_paginate.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'fuel-page'

        response = authenticated_client.get('/tankowania?add=1')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['add_open'] is True

    @patch('backend.routes.fuel.render_template')
    @patch('backend.routes.fuel.paginate')
    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_get_with_date_filter(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_paginate, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_paginate.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'fuel-page'

        response = authenticated_client.get('/tankowania?od=2024-01-01&do=2024-06-30')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['od'] == '2024-01-01'
        assert ctx['do_'] == '2024-06-30'


# ---------------------------------------------------------------------------
# Trips route — additional coverage
# ---------------------------------------------------------------------------

class TestTripsRouteAdditional:
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_post_missing_vehicle_redirects(
        self, mock_db, mock_cur_fn, mock_vehicles, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '',
            'date': '2024-05-01',
            'driver': 'Jan',
            'purpose': 'Pożar',
        })
        assert response.status_code == 302

    @patch('backend.routes.trips.get_active_vehicle')
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_post_invalid_vehicle_redirects(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_active_v, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_active_v.return_value = None

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '999',
            'date': '2024-05-01',
            'driver': 'Jan',
            'purpose': 'Pożar',
        })
        assert response.status_code == 302

    @patch('backend.routes.trips.TripService')
    @patch('backend.routes.trips.parse_trip_equipment_form')
    @patch('backend.routes.trips.get_active_vehicle')
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_post_odo_validation_error_redirects(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_active_v, mock_parse_eq, mock_trip_svc,
        authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_active_v.return_value = {'id': 1}
        mock_parse_eq.return_value = []

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'driver': 'Jan',
            'purpose': 'Pożar',
            'purpose_select': 'Pożar',
            'odo_start': '200',
            'odo_end': '100',  # end < start → validation error
        })
        assert response.status_code == 302
        mock_trip_svc.add_trip.assert_not_called()

    @patch('backend.routes.trips.TripService')
    @patch('backend.routes.trips.parse_trip_equipment_form')
    @patch('backend.routes.trips.get_active_vehicle')
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_post_integrity_error_redirects(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_active_v, mock_parse_eq, mock_trip_svc,
        authenticated_client
    ):
        from psycopg2 import IntegrityError
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_active_v.return_value = {'id': 1}
        mock_parse_eq.return_value = []
        mock_trip_svc.add_trip.side_effect = IntegrityError('constraint')

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'driver': 'Jan',
            'purpose': 'Pożar',
            'purpose_select': 'Pożar',
        })
        assert response.status_code == 302

    @patch('backend.routes.trips.render_template')
    @patch('backend.routes.trips.TripRepository')
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_get_with_add_param_opens_form(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_trip_repository, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_trip_repository.get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'trips-page'

        response = authenticated_client.get('/wyjazdy?add=1&vehicle_id=2')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['add_open'] is True
        assert ctx['selected_vehicle'] == '2'

    @patch('backend.routes.trips.render_template')
    @patch('backend.routes.trips.TripRepository')
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_get_with_date_filters(
        self, mock_db, mock_cur_fn, mock_vehicles, mock_trip_repository, mock_render, authenticated_client
    ):
        mock_db.return_value = MagicMock()
        mock_cur_fn.return_value = _make_cursor()
        mock_vehicles.return_value = []
        mock_trip_repository.get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'trips-page'

        response = authenticated_client.get('/wyjazdy?od=2024-01-01&do=2024-06-30&vehicle_id=3')
        assert response.status_code == 200
        ctx = mock_render.call_args.kwargs
        assert ctx['od'] == '2024-01-01'
        assert ctx['do_'] == '2024-06-30'


# ---------------------------------------------------------------------------
# API route — last_km, drivers, and exception branches
# ---------------------------------------------------------------------------

class TestApiLastKmAndDrivers:
    @patch('backend.routes.api.get_or_set')
    def test_api_last_km_returns_json(self, mock_get_or_set, authenticated_client):
        mock_get_or_set.return_value = (12345, '2024-05-01')

        response = authenticated_client.get('/api/vehicle/1/last_km')
        assert response.status_code == 200
        data = response.get_json()
        assert data['km'] == 12345
        assert data['date'] == '2024-05-01'
        assert isinstance(data['days_ago'], int)

    @patch('backend.routes.api.get_or_set')
    def test_api_last_km_no_data_returns_nulls(self, mock_get_or_set, authenticated_client):
        mock_get_or_set.return_value = (None, None)

        response = authenticated_client.get('/api/vehicle/2/last_km')
        assert response.status_code == 200
        data = response.get_json()
        assert data['km'] is None
        assert data['date'] is None
        assert data['days_ago'] is None

    @patch('backend.routes.api.get_or_set')
    def test_api_last_km_invalid_date_returns_none_days_ago(self, mock_get_or_set, authenticated_client):
        mock_get_or_set.return_value = (5000, 'not-a-date')

        response = authenticated_client.get('/api/vehicle/3/last_km')
        assert response.status_code == 200
        data = response.get_json()
        assert data['days_ago'] is None

    @patch('backend.routes.api.get_or_set')
    def test_api_drivers_returns_list(self, mock_get_or_set, authenticated_client):
        mock_get_or_set.return_value = ['Jan Kowalski', 'Ewa Nowak']

        response = authenticated_client.get('/api/drivers')
        assert response.status_code == 200
        data = response.get_json()
        assert data == ['Jan Kowalski', 'Ewa Nowak']

    def test_api_last_km_requires_login(self, client):
        response = client.get('/api/vehicle/1/last_km')
        assert response.status_code == 302

    def test_api_drivers_requires_login(self, client):
        response = client.get('/api/drivers')
        assert response.status_code == 302


class TestApiExceptionHandling:
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_api_add_trip_unexpected_error_returns_500(
        self, mock_db, mock_cur_fn, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor(fetchone={'id': 1})
        mock_cur_fn.return_value = mock_cur

        with patch('backend.routes.api.TripService') as mock_svc:
            mock_svc.add_trip.side_effect = RuntimeError('DB died')
            response = authenticated_client.post('/api/trips', data={
                '_csrf_token': _csrf(authenticated_client),
                'vehicle_id': '1',
                'date': '2024-05-01',
                'driver': 'Jan',
                'purpose': 'Pożar',
                'purpose_select': 'Pożar',
            })
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_api_add_fuel_unexpected_error_returns_500(
        self, mock_db, mock_cur_fn, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor(fetchone={'id': 1})
        mock_cur.execute.side_effect = [None, RuntimeError('DB boom')]
        mock_cur_fn.return_value = mock_cur

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'driver': 'Jan',
            'liters': '30',
        })
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_api_add_maintenance_unexpected_error_returns_500(
        self, mock_db, mock_cur_fn, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cur = _make_cursor(fetchone={'id': 1})
        mock_cur.execute.side_effect = [None, RuntimeError('DB crash')]
        mock_cur_fn.return_value = mock_cur

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': _csrf(authenticated_client),
            'vehicle_id': '1',
            'date': '2024-05-01',
            'description': 'Serwis',
        })
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False


# ---------------------------------------------------------------------------
# app.py — session timeout, CSRF for JSON, error handler
# ---------------------------------------------------------------------------

class TestSessionTimeout:
    def test_expired_session_redirects_to_login(self, client):
        """Session older than Flask's PERMANENT_SESSION_LIFETIME should be cleared and redirect."""
        # Flask's default PERMANENT_SESSION_LIFETIME is 31 days; use 32 days to exceed it.
        old_time = (datetime.now(timezone.utc) - timedelta(days=32)).isoformat()
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'tester'
            sess['session_started_at'] = old_time
            sess['_csrf_token'] = 'tok'

        response = client.get('/wyjazdy')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_fresh_session_not_redirected(self, client):
        """Session that just started should not be forcibly expired."""
        fresh_time = datetime.now(timezone.utc).isoformat()
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'tester'
            sess['session_started_at'] = fresh_time
            sess['_csrf_token'] = 'tok'

        # Should reach the actual route (may return 200 or be redirected for other reasons,
        # but NOT an expired-session 302 to /login via flash)
        with patch('backend.routes.trips.render_template') as mock_render, \
             patch('backend.routes.trips.TripRepository') as mock_trip_repository, \
             patch('backend.routes.trips.get_vehicles_cached') as mock_v, \
             patch('backend.routes.trips.get_cursor'), \
             patch('backend.routes.trips.get_db'):
            mock_render.return_value = 'ok'
            mock_trip_repository.get_page.return_value = ([], 0, 1, 1)
            mock_v.return_value = []
            response = client.get('/wyjazdy')
        assert response.status_code == 200

    def test_malformed_session_started_at_redirects(self, client):
        """Malformed session_started_at causes session clear and redirect."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['session_started_at'] = 'not-a-datetime'
            sess['_csrf_token'] = 'tok'

        response = client.get('/wyjazdy')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']


class TestCsrfJsonResponse:
    def test_csrf_failure_on_json_request_returns_json(self, client):
        """CSRF failure on a JSON-accepted request should return JSON 403."""
        # Set a CSRF token in session but send a WRONG one in the header
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['_csrf_token'] = 'correct-token'

        response = client.post(
            '/api/trips',
            data={'vehicle_id': '1'},
            headers={'Accept': 'application/json', 'X-CSRFToken': 'wrong-token'},
        )
        assert response.status_code == 403
        data = response.get_json()
        assert data['success'] is False
        assert data['code'] == 'csrf_invalid'

    def test_csrf_failure_on_xmlhttprequest_returns_json(self, client):
        """CSRF failure on XHR request should return JSON 403."""
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['_csrf_token'] = 'correct-token'

        response = client.post(
            '/api/fuel',
            data={'vehicle_id': '1'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': 'wrong-token'},
        )
        assert response.status_code == 403
        data = response.get_json()
        assert data['code'] == 'csrf_invalid'


class TestUnhandledErrorHandler:
    @patch('backend.routes.trips.get_db')
    def test_unexpected_exception_returns_500_html(self, mock_db, authenticated_client):
        """Unhandled exception on a browser route should return 500 HTML."""
        mock_db.side_effect = Exception('unexpected boom')
        response = authenticated_client.get('/wyjazdy')
        assert response.status_code == 500

    @patch('backend.routes.api.get_db')
    def test_unexpected_exception_on_api_route_returns_json(self, mock_db, authenticated_client):
        """Unhandled exception on /api/ route should return JSON 500."""
        mock_db.side_effect = Exception('api boom')
        response = authenticated_client.get('/api/drivers')
        assert response.status_code == 500
        data = response.get_json()
        assert data['ok'] is False


class TestMoreRoute:
    def test_more_page_returns_200_for_authenticated(self, authenticated_client):
        with patch('backend.routes.more.render_template') as mock_render:
            mock_render.return_value = 'more-page'
            response = authenticated_client.get('/wiecej')
        assert response.status_code == 200
