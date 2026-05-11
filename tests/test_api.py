"""Tests for backend/routes/api.py — repository-backed JSON endpoints."""

from unittest.mock import patch

import pytest


class TestValidationHelpers:
    def test_optional_int_valid(self):
        from backend.routes.api import _optional_int

        assert _optional_int('5', 'field') == 5
        assert _optional_int(None, 'field') is None

    def test_optional_float_valid(self):
        from backend.routes.api import _optional_float

        assert _optional_float('3.14', 'field') == pytest.approx(3.14)
        assert _optional_float('', 'field') is None

    def test_parse_trip_equipment_form_valid(self):
        from backend.helpers import parse_trip_equipment_form

        class DummyForm:
            def getlist(self, key):
                values = {
                    'eq_id[]': ['1'],
                    'eq_qty[]': ['2'],
                    'eq_min[]': ['30'],
                }
                return values.get(key, [])

        assert parse_trip_equipment_form(DummyForm()) == [
            {'equipment_id': 1, 'quantity_used': 2, 'minutes_used': 30},
        ]


class TestApiTripEndpoint:
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_trip_missing_vehicle_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '999',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': 'Test',
        })

        assert response.status_code == 400
        assert response.get_json()['success'] is False

    @patch('backend.routes.api.AuditService')
    @patch('backend.routes.api.TripRepository')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_trip_success(self, mock_get_active, mock_trip_repository, mock_audit, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan Kowalski',
            'purpose_select': 'Ćwiczenia',
            'odo_start': '1000',
            'odo_end': '1050',
        })

        assert response.status_code == 200
        assert response.get_json()['success'] is True
        mock_trip_repository.add.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_trip_with_equipment_missing_minutes_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': 'Test',
            'eq_id[]': ['10'],
            'eq_min[]': [''],
        })

        assert response.status_code == 400


class TestApiFuelEndpoint:
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_fuel_missing_vehicle_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '999',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '50',
        })

        assert response.status_code == 400

    @patch('backend.routes.api.AuditService')
    @patch('backend.routes.api.FuelRepository')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_fuel_success(self, mock_get_active, mock_fuel_repository, mock_audit, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '30',
            'cost': '100',
            'odometer': '15000',
        })

        assert response.status_code == 200
        assert response.get_json()['success'] is True
        mock_fuel_repository.add.assert_called_once()
        mock_audit.log.assert_called_once()


class TestApiMaintenanceEndpoint:
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_maintenance_missing_vehicle_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '999',
            'date': '2024-01-01',
            'description': 'Test',
        })

        assert response.status_code == 400

    @patch('backend.routes.api.AuditService')
    @patch('backend.routes.api.MaintenanceRepository')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_maintenance_success(self, mock_get_active, mock_maintenance_repository, mock_audit, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'description': 'Wymiana oleju',
            'priority': 'high',
            'status': 'pending',
        })

        assert response.status_code == 200
        assert response.get_json()['success'] is True
        mock_maintenance_repository.add.assert_called_once()
        mock_audit.log.assert_called_once()


class TestApiSupportEndpoints:
    @patch('backend.routes.api.get_or_set')
    def test_last_km_returns_json(self, mock_get_or_set, authenticated_client):
        mock_get_or_set.return_value = (12345, '2024-05-01')

        response = authenticated_client.get('/api/vehicle/1/last_km')

        assert response.status_code == 200
        data = response.get_json()
        assert data['km'] == 12345
        assert data['date'] == '2024-05-01'
        assert isinstance(data['days_ago'], int)

    @patch('backend.routes.api.get_or_set')
    def test_drivers_returns_list(self, mock_get_or_set, authenticated_client):
        mock_get_or_set.return_value = ['Jan', 'Anna']

        response = authenticated_client.get('/api/drivers')

        assert response.status_code == 200
        assert response.get_json() == ['Jan', 'Anna']

    def test_support_endpoints_require_login(self, client):
        assert client.get('/api/drivers').status_code == 302
        assert client.get('/api/vehicle/1/last_km').status_code == 302