"""Focused coverage tests for app-level behavior and error handlers."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class TestSessionTimeout:
    def test_expired_session_redirects_to_login(self, client):
        old_time = (datetime.now(timezone.utc) - timedelta(days=32)).isoformat()
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'tester'
            sess['session_started_at'] = old_time
            sess['_csrf_token'] = 'tok'

        response = client.get('/wyjazdy')

        assert response.status_code == 302
        assert '/login' in response.headers['Location']


class TestCsrfJsonResponse:
    def test_csrf_failure_on_json_request_returns_json(self, client):
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['_csrf_token'] = 'correct-token'

        response = client.post(
            '/api/trips',
            data={'vehicle_id': '1'},
            headers={'Accept': 'application/json', 'X-CSRFToken': 'wrong-token'},
        )

        assert response.status_code == 403
        assert response.get_json()['code'] == 'csrf_invalid'


class TestUnhandledErrorHandler:
    @patch('backend.routes.trips.TripRepository.get_page')
    def test_browser_route_unhandled_exception_returns_500(self, mock_get_page, authenticated_client):
        mock_get_page.side_effect = RuntimeError('unexpected boom')

        response = authenticated_client.get('/wyjazdy')

        assert response.status_code == 500

    @patch('backend.routes.api.TripRepository.add')
    @patch('backend.routes.api.VehicleRepository.get_active')
    def test_api_route_unhandled_exception_returns_json_500(self, mock_get_active, mock_add, authenticated_client):
        mock_get_active.return_value = {'id': 1}
        mock_add.side_effect = RuntimeError('api boom')

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post('/api/trips', data={
            '_csrf_token': csrf,
            'vehicle_id': '1',
            'date': '2024-05-01',
            'driver': 'Jan',
            'purpose': 'Pożar',
        })

        assert response.status_code == 500
        assert response.get_json()['success'] is False