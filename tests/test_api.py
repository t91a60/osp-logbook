"""Tests for backend/routes/api.py — JSON API endpoint validation."""

import pytest
from unittest.mock import patch, MagicMock


class TestValidationHelpers:
    """Test the module-level validation helpers in api.py."""

    def test_optional_int_valid(self):
        from backend.routes.api import _optional_int
        assert _optional_int('5', 'field') == 5
        assert _optional_int(10, 'field') == 10

    def test_optional_int_none_and_empty(self):
        from backend.routes.api import _optional_int
        assert _optional_int(None, 'field') is None
        assert _optional_int('', 'field') is None

    def test_optional_int_invalid_raises(self):
        from backend.routes.api import _optional_int, ValidationError
        with pytest.raises(ValidationError):
            _optional_int('abc', 'test_field')

    def test_optional_float_valid(self):
        from backend.routes.api import _optional_float
        assert _optional_float('3.14', 'field') == pytest.approx(3.14)
        assert _optional_float(2.5, 'field') == pytest.approx(2.5)

    def test_optional_float_none_and_empty(self):
        from backend.routes.api import _optional_float
        assert _optional_float(None, 'field') is None
        assert _optional_float('', 'field') is None

    def test_optional_float_invalid_raises(self):
        from backend.routes.api import _optional_float, ValidationError
        with pytest.raises(ValidationError):
            _optional_float('not-a-number', 'cost')

    def test_parse_trip_equipment_valid(self):
        from backend.routes.api import _parse_trip_equipment

        class DummyForm:
            def getlist(self, key):
                values = {
                    'eq_id[]': ['1', '2'],
                    'eq_qty[]': ['1', '1'],
                    'eq_min[]': ['15', '45'],
                }
                return values.get(key, [])

        assert _parse_trip_equipment(DummyForm()) == [
            {'equipment_id': 1, 'quantity_used': 1, 'minutes_used': 15},
            {'equipment_id': 2, 'quantity_used': 1, 'minutes_used': 45},
        ]

    def test_parse_trip_equipment_missing_minutes_raises(self):
        from backend.routes.api import _parse_trip_equipment, ValidationError

        class DummyForm:
            def getlist(self, key):
                values = {
                    'eq_id[]': ['1'],
                    'eq_qty[]': ['1'],
                    'eq_min[]': [''],
                }
                return values.get(key, [])

        with pytest.raises(ValidationError):
            _parse_trip_equipment(DummyForm())

    def test_get_active_vehicle_valid(self):
        from backend.routes.api import _get_active_vehicle
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {'id': 1}
        result = _get_active_vehicle(mock_cur, '1')
        assert result == {'id': 1}

    def test_get_active_vehicle_invalid_id(self):
        from backend.routes.api import _get_active_vehicle
        mock_cur = MagicMock()
        result = _get_active_vehicle(mock_cur, 'abc')
        assert result is None

    def test_get_active_vehicle_not_found(self):
        from backend.routes.api import _get_active_vehicle
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        result = _get_active_vehicle(mock_cur, '999')
        assert result is None

    def test_get_active_vehicle_none_id(self):
        from backend.routes.api import _get_active_vehicle
        mock_cur = MagicMock()
        result = _get_active_vehicle(mock_cur, None)
        assert result is None


class TestApiTripEndpoint:
    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_missing_vehicle(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips with invalid vehicle returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # Vehicle not found

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
        data = response.get_json()
        assert data['success'] is False

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_missing_driver(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips without driver returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': '',
            'purpose': 'Test',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_missing_date(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips without date returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'driver': 'Jan',
            'purpose': 'Test',
            'date': '',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_missing_purpose(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips without purpose returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose': '',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_success(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips with all required fields succeeds."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan Kowalski',
            'purpose': 'Ćwiczenia',
            'odo_start': '10000',
            'odo_end': '10050',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_custom_purpose(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips with purpose_select=__inne__ uses purpose_custom."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'purpose_select': '__inne__',
            'purpose_custom': 'Custom Purpose',
        })
        assert response.status_code == 200
        # Verify TripService.add_trip was called with the custom purpose
        mock_trip_service.add_trip.assert_called_once()
        call_args = mock_trip_service.add_trip.call_args
        # The 'purpose' argument is passed positionally; verify it contains the custom purpose
        all_args = list(call_args[0]) + list(call_args[1].values())
        assert 'Custom Purpose' in all_args

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_with_equipment_usage(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips maps equipment usage with minutes to TripService."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan Kowalski',
            'purpose': 'Ćwiczenia',
            'eq_id[]': ['10', '11'],
            'eq_qty[]': ['1', '1'],
            'eq_min[]': ['20', '35'],
        })
        assert response.status_code == 200
        call_kwargs = mock_trip_service.add_trip.call_args.kwargs
        assert call_kwargs['equipment_used'] == [
            {'equipment_id': 10, 'quantity_used': 1, 'minutes_used': 20},
            {'equipment_id': 11, 'quantity_used': 1, 'minutes_used': 35},
        ]

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_with_equipment_missing_minutes_returns_400(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips with incomplete equipment row returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan Kowalski',
            'purpose': 'Ćwiczenia',
            'eq_id[]': ['10'],
            'eq_min[]': [''],
        })
        assert response.status_code == 400
        mock_trip_service.add_trip.assert_not_called()

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_with_equipment_non_integer_minutes_returns_400(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips with non-integer equipment minutes returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan Kowalski',
            'purpose': 'Ćwiczenia',
            'eq_id[]': ['10'],
            'eq_min[]': ['10.5'],
        })
        assert response.status_code == 400
        mock_trip_service.add_trip.assert_not_called()

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_with_equipment_zero_minutes_returns_400(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """POST /api/trips with zero equipment minutes returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan Kowalski',
            'purpose': 'Ćwiczenia',
            'eq_id[]': ['10'],
            'eq_min[]': ['0'],
        })
        assert response.status_code == 400
        mock_trip_service.add_trip.assert_not_called()

    def test_add_trip_requires_login(self, client):
        """POST /api/trips without login redirects to login."""
        response = client.post('/api/trips', data={'vehicle_id': '1'})
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestApiFuelEndpoint:
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_missing_liters(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel without liters returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_zero_liters(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel with liters=0 returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '0',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_negative_liters(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel with negative liters returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan',
            'liters': '-5',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_success(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel with valid data succeeds."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': 'Jan Kowalski',
            'liters': '50.5',
            'cost': '320.00',
            'odometer': '15000',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_missing_driver(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel without driver returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/fuel', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'driver': '',
            'liters': '50',
        })
        assert response.status_code == 400


class TestApiMaintenanceEndpoint:
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_missing_description(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/maintenance without description returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'description': '',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_success(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/maintenance with valid data succeeds."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'description': 'Wymiana oleju',
            'priority': 'high',
            'status': 'pending',
            'cost': '250',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_invalid_priority_defaults(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/maintenance with invalid priority defaults to 'medium'."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'description': 'Test serwis',
            'priority': 'invalid_priority',
            'status': 'pending',
        })
        assert response.status_code == 200

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_invalid_status_defaults(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/maintenance with invalid status defaults to 'pending'."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-01-01',
            'description': 'Test serwis',
            'priority': 'medium',
            'status': 'invalid_status',
        })
        assert response.status_code == 200

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_missing_date(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/maintenance without date returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '',
            'description': 'Test',
        })
        assert response.status_code == 400
