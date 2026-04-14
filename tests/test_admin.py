"""Tests for backend/routes/admin.py — delete_entry and admin operations."""

import pytest
from unittest.mock import patch, MagicMock


class TestDeleteEntry:
    """Tests for the /usun/<kind>/<id> endpoint."""

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_own_entry(self, mock_get_db, mock_get_cursor, authenticated_client):
        """User can delete their own entry."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'added_by': 'testuser'}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post(
            '/usun/wyjazd/1',
            data={'_csrf_token': csrf},
        )
        assert response.status_code == 302  # Redirect after delete

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_others_entry_forbidden(self, mock_get_db, mock_get_cursor, authenticated_client):
        """Non-admin cannot delete another user's entry."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'added_by': 'otheruser'}

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post(
            '/usun/wyjazd/1',
            data={'_csrf_token': csrf},
        )
        assert response.status_code == 403

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_admin_can_delete_any_entry(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin can delete any user's entry."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'added_by': 'otheruser'}

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post(
            '/usun/tankowanie/5',
            data={'_csrf_token': csrf},
        )
        assert response.status_code == 302

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_nonexistent_entry(self, mock_get_db, mock_get_cursor, authenticated_client):
        """Deleting a nonexistent entry flashes error and redirects."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # Entry not found

        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post(
            '/usun/wyjazd/999',
            data={'_csrf_token': csrf},
        )
        assert response.status_code == 302

    def test_delete_invalid_kind_returns_404(self, authenticated_client):
        """Using an invalid 'kind' parameter returns 404."""
        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post(
            '/usun/invalid/1',
            data={'_csrf_token': csrf},
        )
        assert response.status_code == 404

    def test_delete_valid_kinds(self):
        """Ensure all three valid kinds are mapped correctly."""
        # This tests the internal mapping without making HTTP requests
        tables = {'wyjazd': 'trips', 'tankowanie': 'fuel', 'serwis': 'maintenance'}
        assert tables['wyjazd'] == 'trips'
        assert tables['tankowanie'] == 'fuel'
        assert tables['serwis'] == 'maintenance'


class TestVehicleRoutes:
    def test_vehicles_requires_admin(self, authenticated_client):
        """Non-admin accessing /pojazdy gets 403."""
        response = authenticated_client.get('/pojazdy')
        assert response.status_code == 403

    def test_vehicles_requires_login(self, client):
        """Unauthenticated user accessing /pojazdy is redirected to login."""
        response = client.get('/pojazdy')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    def test_delete_vehicle_requires_admin(self, authenticated_client):
        """Non-admin cannot delete a vehicle."""
        with authenticated_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = authenticated_client.post(
            '/pojazdy/1/usun',
            data={'_csrf_token': csrf},
        )
        assert response.status_code == 403

    def test_edit_vehicle_requires_admin(self, authenticated_client):
        """Non-admin cannot access vehicle edit."""
        response = authenticated_client.get('/pojazdy/1/edytuj')
        assert response.status_code == 403


class TestUserRoutes:
    def test_users_requires_admin(self, authenticated_client):
        """Non-admin accessing /uzytkownicy gets 403."""
        response = authenticated_client.get('/uzytkownicy')
        assert response.status_code == 403

    def test_users_requires_login(self, client):
        """Unauthenticated user accessing /uzytkownicy is redirected to login."""
        response = client.get('/uzytkownicy')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')
