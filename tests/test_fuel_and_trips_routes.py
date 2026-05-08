"""Tests for fuel/trips route helpers and selected route flows."""

from unittest.mock import patch, MagicMock
import pytest


class TestFuelHelpers:
    def test_require_float_accepts_valid_values(self):
        from backend.routes.fuel import _require_float
        assert _require_float('3.5', 'Litry') == pytest.approx(3.5)
        assert _require_float(None, 'Litry') is None

    def test_require_float_rejects_invalid_value(self):
        from backend.routes.fuel import _require_float, ValidationError
        with pytest.raises(ValidationError, match='Litry musi być liczbą'):
            _require_float('abc', 'Litry')

    def test_require_int_accepts_valid_values(self):
        from backend.routes.fuel import _require_int
        assert _require_int('10', 'Stan km') == 10
        assert _require_int('', 'Stan km') is None

    def test_require_int_rejects_invalid_value(self):
        from backend.routes.fuel import _require_int, ValidationError
        with pytest.raises(ValidationError, match='Stan km musi być liczbą całkowitą'):
            _require_int('abc', 'Stan km')


class TestTripsHelpers:
    def test_require_int_accepts_valid_values(self):
        from backend.routes.trips import _require_int
        assert _require_int('12', 'Km start') == 12
        assert _require_int(None, 'Km start') is None

    def test_require_int_rejects_invalid_value(self):
        from backend.routes.trips import _require_int, ValidationError
        with pytest.raises(ValidationError, match='Km start musi być liczbą całkowitą'):
            _require_int('x', 'Km start')


class TestFuelRoutes:
    @patch('backend.routes.fuel.render_template')
    @patch('backend.routes.fuel.paginate')
    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_get_renders_with_paginated_data(
        self, mock_get_db, mock_get_cursor, mock_get_vehicles, mock_paginate, mock_render, authenticated_client
    ):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_get_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_paginate.return_value = ([{'id': 1}], 1, 1, 1)
        mock_render.return_value = 'fuel-page'

        response = authenticated_client.get('/tankowania?vehicle_id=1')

        assert response.status_code == 200
        assert response.data == b'fuel-page'
        context = mock_render.call_args.kwargs
        assert context['selected_vehicle'] == '1'
        assert context['total'] == 1
        mock_cur.close.assert_called_once()

    @patch('backend.routes.fuel.get_vehicles_cached')
    @patch('backend.routes.fuel.get_cursor')
    @patch('backend.routes.fuel.get_db')
    def test_fuel_post_invalid_liters_redirects_with_error(self, mock_get_db, mock_get_cursor, mock_get_vehicles, authenticated_client):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_get_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/tankowania', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '0',
        })

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/tankowania')
        mock_cur.execute.assert_not_called()
        mock_conn.commit.assert_not_called()


class TestTripsRoutes:
    @patch('backend.routes.trips.parse_trip_equipment_form')
    @patch('backend.routes.trips.TripService')
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_post_custom_purpose_calls_service(
        self,
        mock_get_db,
        mock_get_cursor,
        mock_get_vehicles,
        mock_trip_service,
        mock_parse_trip_equipment_form,
        authenticated_client,
    ):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_get_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_parse_trip_equipment_form.return_value = []

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/wyjazdy', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose_select': '__inne__',
            'purpose_custom': 'Alarm pożarowy',
            'odo_start': '1000',
            'odo_end': '1010',
        })

        assert response.status_code == 302
        assert '/wyjazdy' in response.headers.get('Location', '')
        assert mock_trip_service.add_trip.call_args.args[5] == 'Alarm pożarowy'
        mock_cur.close.assert_called_once()

    @patch('backend.routes.trips.parse_trip_equipment_form')
    @patch('backend.routes.trips.get_vehicles_cached')
    @patch('backend.routes.trips.get_cursor')
    @patch('backend.routes.trips.get_db')
    def test_trips_post_invalid_equipment_form_rolls_back(
        self,
        mock_get_db,
        mock_get_cursor,
        mock_get_vehicles,
        mock_parse_trip_equipment_form,
        authenticated_client,
    ):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_get_vehicles.return_value = [{'id': 1, 'name': 'GBA'}]
        mock_parse_trip_equipment_form.side_effect = ValueError('Niepoprawny sprzęt')

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
        assert response.headers['Location'].endswith('/wyjazdy')
        mock_conn.rollback.assert_called_once()
