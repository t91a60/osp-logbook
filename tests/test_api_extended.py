"""Extended tests for API endpoints — maintenance validation, fuel missing vehicle/date."""

from unittest.mock import patch, MagicMock


class TestApiMaintenanceValidation:
    """Additional validation tests for POST /api/maintenance."""

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_missing_vehicle(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/maintenance with invalid vehicle returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # Vehicle not found

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/maintenance', data={
            '_csrf_token': csrf,
            'vehicle_id': '999',
            'date': '2024-01-01',
            'description': 'Test',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

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
            'description': 'Oil change',
            'date': '',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_invalid_priority_defaults_to_medium(self, mock_get_db, mock_get_cursor, authenticated_client):
        """Invalid priority value defaults to 'medium'."""
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
            'description': 'Test maintenance',
            'priority': 'invalid_priority',
            'status': 'pending',
        })
        assert response.status_code == 200
        # The route normalizes invalid priority to 'medium'
        data = response.get_json()
        assert data['success'] is True

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_invalid_status_defaults_to_pending(self, mock_get_db, mock_get_cursor, authenticated_client):
        """Invalid status value defaults to 'pending'."""
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
            'description': 'Test maintenance',
            'priority': 'high',
            'status': 'invalid_status',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_maintenance_with_due_date(self, mock_get_db, mock_get_cursor, authenticated_client):
        """Maintenance with due_date succeeds."""
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
            'description': 'Scheduled service',
            'priority': 'low',
            'due_date': '2024-04-01',
        })
        assert response.status_code == 200

    def test_add_maintenance_requires_login(self, client):
        """POST /api/maintenance without login redirects."""
        response = client.post('/api/maintenance', data={'vehicle_id': '1'})
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestApiFuelExtended:
    """Extended fuel API validation tests."""

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_missing_vehicle(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel with invalid vehicle returns 400."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # Vehicle not found

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
        data = response.get_json()
        assert data['success'] is False

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_missing_date(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel without date returns 400."""
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
            'driver': 'Jan',
            'liters': '50',
            'date': '',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_non_numeric_liters(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel with non-numeric liters returns 400."""
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
            'liters': 'abc',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_fuel_with_optional_fields_empty(self, mock_get_db, mock_get_cursor, authenticated_client):
        """POST /api/fuel with minimal required fields and empty optional fields succeeds."""
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
            'liters': '30',
            'cost': '',
            'odometer': '',
            'notes': '',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_add_fuel_requires_login(self, client):
        """POST /api/fuel without login redirects."""
        response = client.post('/api/fuel', data={'vehicle_id': '1'})
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')


class TestApiTripExtended:
    """Extended trip API tests."""

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_invalid_odo_start(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """Non-integer odo_start returns 400."""
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
            'purpose': 'Test',
            'odo_start': 'abc',
        })
        assert response.status_code == 400

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_with_time_fields(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """Trip with time_start/time_end passes them to service."""
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
            'purpose': 'Test',
            'time_start': '08:00',
            'time_end': '16:00',
        })
        assert response.status_code == 200
        call_kwargs = mock_trip_service.add_trip.call_args.kwargs
        assert call_kwargs['time_start'] == '08:00'
        assert call_kwargs['time_end'] == '16:00'

    @patch('backend.routes.api.TripService')
    @patch('backend.routes.api.get_cursor')
    @patch('backend.routes.api.get_db')
    def test_add_trip_purpose_from_purpose_select(self, mock_get_db, mock_get_cursor, mock_trip_service, authenticated_client):
        """purpose_select value is used when not '__inne__'."""
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
            'purpose_select': 'Ćwiczenia',
        })
        assert response.status_code == 200
        call_args = mock_trip_service.add_trip.call_args[0]
        assert 'Ćwiczenia' in call_args
