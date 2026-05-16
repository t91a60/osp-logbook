"""Route smoke tests for /wyjazdy and /tankowania."""

from unittest.mock import MagicMock, patch

import pytest

from backend.domain.exceptions import NotFoundError, ForbiddenError
from psycopg2 import IntegrityError


class TestTripsRoute:
    @patch('backend.routes.trips.render_template')
    @patch('backend.routes.trips.GetTripsUseCase.execute')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_get_renders(self, mock_vehicles, mock_get_page, mock_render, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'trips-page'

        response = authenticated_client.get('/wyjazdy')

        assert response.status_code == 200
        assert response.data == b'trips-page'

    @patch('backend.routes.trips.AddTripUseCase.execute')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_post_valid_data_creates_trip(self, mock_vehicles, mock_execute, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]

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
        mock_execute.assert_called_once()

    @patch('backend.routes.trips.get_vehicles_cached')
    def test_post_missing_vehicle_returns_400(self, mock_vehicles, authenticated_client):
        mock_vehicles.return_value = []

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

    @patch('backend.routes.trips.AddTripUseCase.execute')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_post_handles_integrity_error(self, mock_vehicles, mock_execute, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_execute.side_effect = IntegrityError()

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': 'Ćwiczenia',
        })

        assert response.status_code == 302

    @patch('backend.routes.trips.AddTripUseCase.execute')
    @patch('backend.routes.trips.parse_trip_equipment_form')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_post_invalid_equipment_form(self, mock_vehicles, mock_parse_equipment, mock_execute, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_parse_equipment.side_effect = ValueError('bad equipment')

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': 'Ćwiczenia',
        })

        assert response.status_code == 302
        mock_execute.assert_not_called()

    @patch('backend.routes.trips.AddTripUseCase.execute')
    @patch('backend.routes.trips.get_vehicles_cached')
    def test_post_uses_custom_purpose(self, mock_vehicles, mock_execute, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose_select': '__inne__',
            'purpose_custom': 'Wyjazd gospodarczy',
        })

        assert response.status_code == 302
        cmd = mock_execute.call_args.args[0]
        assert cmd.purpose == 'Wyjazd gospodarczy'


class TestFuelRoute:
    @patch('backend.routes.fuel.render_template')
    @patch('backend.routes.fuel.GetFuelUseCase.execute')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_get_renders(self, mock_vehicles, mock_get_page, mock_render, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_page.return_value = ([], 0, 1, 1)
        mock_render.return_value = 'fuel-page'

        response = authenticated_client.get('/tankowania')

        assert response.status_code == 200
        assert response.data == b'fuel-page'

    @patch('backend.routes.fuel.AddFuelUseCase.execute')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_post_valid_data_creates_entry(self, mock_vehicles, mock_execute, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]

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
        mock_execute.assert_called_once()

    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_post_missing_vehicle_returns_400(self, mock_vehicles, authenticated_client):
        mock_vehicles.return_value = []

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

    @patch('backend.routes.fuel.GetFuelByIdUseCase.execute')
    def test_edit_get_missing_entry_redirects(self, mock_get_entry, authenticated_client):
        mock_get_entry.return_value = None

        response = authenticated_client.get('/tankowania/10/edytuj')

        assert response.status_code == 302
        assert '/tankowania' in response.headers['Location']

    @patch('backend.routes.fuel.GetFuelByIdUseCase.execute')
    def test_edit_get_forbidden_redirects(self, mock_get_entry, authenticated_client):
        mock_get_entry.return_value = {'id': 10, 'added_by': 'other'}

        response = authenticated_client.get('/tankowania/10/edytuj')

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/')

    @patch('backend.routes.fuel.GetFuelByIdUseCase.execute')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_edit_post_missing_vehicle(self, mock_vehicles, mock_get_entry, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_entry.return_value = {'id': 10, 'added_by': 'testuser'}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania/10/edytuj', data={
            '_csrf_token': csrf,
            'vehicle_id': '',
            'date': '2024-01-01',
            'driver': 'Jan',
        })

        assert response.status_code == 302

    @patch('backend.routes.fuel.EditFuelUseCase.execute')
    @patch('backend.routes.fuel.GetFuelByIdUseCase.execute')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_edit_post_handles_not_found(self, mock_vehicles, mock_get_entry, mock_edit, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_entry.return_value = {'id': 10, 'added_by': 'testuser'}
        mock_edit.side_effect = NotFoundError('missing')

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania/10/edytuj', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
        })

        assert response.status_code == 302

    @patch('backend.routes.fuel.EditFuelUseCase.execute')
    @patch('backend.routes.fuel.GetFuelByIdUseCase.execute')
    @patch('backend.routes.fuel.get_vehicles_cached')
    def test_edit_post_success(self, mock_vehicles, mock_get_entry, mock_edit, authenticated_client):
        mock_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_get_entry.return_value = {'id': 10, 'added_by': 'testuser'}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania/10/edytuj', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
        })

        assert response.status_code == 302
        mock_edit.assert_called_once()

    @patch('backend.routes.fuel.DeleteFuelUseCase.execute')
    def test_delete_handles_not_found(self, mock_delete, authenticated_client):
        mock_delete.side_effect = NotFoundError('missing')

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania/10/usun', data={'_csrf_token': csrf})

        assert response.status_code == 302

    @patch('backend.routes.fuel.DeleteFuelUseCase.execute')
    def test_delete_handles_forbidden(self, mock_delete, authenticated_client):
        mock_delete.side_effect = ForbiddenError('forbidden')

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania/10/usun', data={'_csrf_token': csrf})

        assert response.status_code == 302
