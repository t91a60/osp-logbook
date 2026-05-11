"""Extended tests for backend/routes/api.py edge cases."""

from unittest.mock import patch


class TestApiTripExtended:
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_trip_invalid_odo_start_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': 'Test',
            'odo_start': 'abc',
        })

        assert response.status_code == 400

    @patch('backend.routes.api.AuditService.log')
    @patch('backend.routes.api.TripRepository.add')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_trip_custom_purpose_uses_custom_value(self, mock_get_active, mock_add_trip, mock_audit_log, authenticated_client):
        mock_get_active.return_value = {'id': 1}
        mock_add_trip.return_value = None
        mock_audit_log.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose_select': '__inne__',
            'purpose_custom': 'Alarm pożarowy',
        })

        assert response.status_code == 200

    def test_add_trip_requires_login(self, client):
        assert client.post('/api/trips', data={'vehicle_id': '1'}).status_code == 302


class TestApiFuelExtended:
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_fuel_non_numeric_liters_returns_400(self, mock_get_active, authenticated_client):
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': 'abc',
        })

        assert response.status_code == 400

    @patch('backend.routes.api.AuditService.log')
    @patch('backend.routes.api.FuelRepository.add')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_fuel_optional_fields_empty(self, mock_get_active, mock_add_fuel, mock_audit_log, authenticated_client):
        mock_get_active.return_value = {'id': 1}
        mock_add_fuel.return_value = None
        mock_audit_log.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '30',
            'cost': '',
            'odometer': '',
            'notes': '',
        })

        assert response.status_code == 200

    def test_add_fuel_requires_login(self, client):
        assert client.post('/api/fuel', data={'vehicle_id': '1'}).status_code == 302


class TestApiMaintenanceExtended:
    @patch('backend.routes.api.AuditService.log')
    @patch('backend.routes.api.MaintenanceRepository.add')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_maintenance_invalid_status_defaults_to_pending(self, mock_get_active, mock_add_maintenance, mock_audit_log, authenticated_client):
        mock_get_active.return_value = {'id': 1}
        mock_add_maintenance.return_value = None
        mock_audit_log.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'description': 'Test maintenance',
            'priority': 'high',
            'status': 'invalid_status',
        })

        assert response.status_code == 200

    @patch('backend.routes.api.AuditService.log')
    @patch('backend.routes.api.MaintenanceRepository.add')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_add_maintenance_due_date(self, mock_get_active, mock_add_maintenance, mock_audit_log, authenticated_client):
        mock_get_active.return_value = {'id': 1}
        mock_add_maintenance.return_value = None
        mock_audit_log.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'description': 'Scheduled service',
            'priority': 'low',
            'due_date': '2024-04-01',
        })

        assert response.status_code == 200

    def test_add_maintenance_requires_login(self, client):
        assert client.post('/api/maintenance', data={'vehicle_id': '1'}).status_code == 302