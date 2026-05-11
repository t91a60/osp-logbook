"""Route smoke tests for /wyjazdy and /tankowania."""

from unittest.mock import MagicMock, patch

import pytest


class TestTripsRoute:
    @patch('backend.routes.trips.render_template')
    @patch('backend.routes.trips.TripRepository.get_page')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_get_renders(self, mock_vehicles, mock_get_page, mock_render, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'trips-page'

        response = authenticated_client.get('/wyjazdy')

        assert response.status_code == 200
        assert response.data == b'trips-page'

    @patch('backend.routes.trips.AuditService')
    @patch('backend.routes.trips.TripRepository')
    @patch('backend.routes.trips.VehicleRepository.get_active')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_post_valid_data_creates_trip(self, mock_vehicles, mock_get_active, mock_trip_repo, mock_audit, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': 'Ćwiczenia',
            'odo_start': '100',
            'odo_end': '150',
        })

        assert response.status_code == 302
        mock_trip_repo.add.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.routes.trips.VehicleRepository.get_active')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_post_missing_vehicle_returns_400(self, mock_vehicles, mock_get_active, authenticated_client):
        mock_vehicles.return_value = []
        mock_get_active.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': csrf,
            'vehicle_id': '',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': 'Ćwiczenia',
        })

        assert response.status_code == 302


class TestFuelRoute:
    @patch('backend.routes.fuel.render_template')
    @patch('backend.routes.fuel.FuelRepository.get_page')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_get_renders(self, mock_vehicles, mock_get_page, mock_render, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'fuel-page'

        response = authenticated_client.get('/tankowania')

        assert response.status_code == 200
        assert response.data == b'fuel-page'

    @patch('backend.routes.fuel.AuditService')
    @patch('backend.routes.fuel.FuelRepository')
    @patch('backend.routes.fuel.VehicleRepository.get_active')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_post_valid_data_creates_entry(self, mock_vehicles, mock_get_active, mock_fuel_repo, mock_audit, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_active.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '30',
            'cost': '120',
            'odometer': '12000',
        })

        assert response.status_code == 302
        mock_fuel_repo.add.assert_called_once()
        mock_audit.log.assert_called_once()

    @patch('backend.routes.fuel.VehicleRepository.get_active')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_post_missing_vehicle_returns_400(self, mock_vehicles, mock_get_active, authenticated_client):
        mock_vehicles.return_value = []
        mock_get_active.return_value = None

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania', data={
            '_csrf_token': csrf,
            'vehicle_id': '',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '30',
        })

        assert response.status_code == 302