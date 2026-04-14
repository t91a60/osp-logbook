"""Tests for backend/routes/auth.py — login/logout flows."""

import pytest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash


class TestLoginRoute:
    def test_login_page_renders(self, client):
        """GET /login returns 200 with login page."""
        response = client.get('/login')
        assert response.status_code == 200

    def test_already_logged_in_redirects_to_dashboard(self, authenticated_client):
        """If already logged in, GET /login redirects to dashboard."""
        response = authenticated_client.get('/login')
        assert response.status_code == 302
        assert '/' in response.headers.get('Location', '')

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_successful_login_sets_session(self, mock_get_db, mock_get_cursor, client):
        """Successful login populates session and redirects to dashboard."""
        # Set up CSRF
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'token123'

        # Mock DB to return a valid user
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 42,
            'username': 'testuser',
            'password': generate_password_hash('correct-password'),
            'display_name': 'Test User',
            'is_admin': False,
        }

        response = client.post('/login', data={
            '_csrf_token': 'token123',
            'username': 'testuser',
            'password': 'correct-password',
        })

        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess['user_id'] == 42
            assert sess['username'] == 'testuser'
            assert sess['display_name'] == 'Test User'
            assert sess['is_admin'] is False
            assert '_csrf_token' in sess

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_failed_login_shows_error(self, mock_get_db, mock_get_cursor, client):
        """Wrong password shows error flash message."""
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'token123'

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 1,
            'username': 'testuser',
            'password': generate_password_hash('real-password'),
            'display_name': 'Test User',
            'is_admin': False,
        }

        response = client.post('/login', data={
            '_csrf_token': 'token123',
            'username': 'testuser',
            'password': 'wrong-password',
        })

        # Should re-render login page (200), not redirect to dashboard
        assert response.status_code == 200

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_nonexistent_user_shows_error(self, mock_get_db, mock_get_cursor, client):
        """Login attempt with nonexistent user shows error."""
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'token123'

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # User not found

        response = client.post('/login', data={
            '_csrf_token': 'token123',
            'username': 'ghost',
            'password': 'doesntmatter',
        })

        assert response.status_code == 200

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_admin_auto_repair_flag(self, mock_get_db, mock_get_cursor, client):
        """User named 'admin' without is_admin flag gets auto-repaired."""
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'token123'

        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur

        # First call: SELECT user (is_admin=False for user named 'admin')
        # Second call: UPDATE returning is_admin=True
        mock_cur.fetchone.side_effect = [
            {
                'id': 1,
                'username': 'admin',
                'password': generate_password_hash('adminpass'),
                'display_name': 'Admin',
                'is_admin': False,
            },
            {'is_admin': True},  # UPDATE RETURNING result
        ]

        response = client.post('/login', data={
            '_csrf_token': 'token123',
            'username': 'admin',
            'password': 'adminpass',
        })

        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess['is_admin'] is True


class TestLogoutRoute:
    def test_logout_clears_session(self, authenticated_client):
        """GET /logout clears the session and redirects to login."""
        response = authenticated_client.get('/logout')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

        with authenticated_client.session_transaction() as sess:
            assert 'user_id' not in sess
            assert 'username' not in sess

    def test_logout_when_not_logged_in(self, client):
        """Logging out without a session still redirects to login."""
        response = client.get('/logout')
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')
