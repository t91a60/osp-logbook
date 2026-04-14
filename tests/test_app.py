"""Tests for app.py — application factory, security headers, health, CSRF."""

import os
import pytest
from unittest.mock import patch, MagicMock
from flask import session, g

from app import create_app


class TestCreateApp:
    def test_app_is_created(self, app):
        assert app is not None
        assert app.config['TESTING'] is True

    def test_secret_key_is_set(self, app):
        assert app.config['SECRET_KEY'] == 'test-secret-key-for-testing'

    def test_health_endpoint_registered(self, app):
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        assert 'health' in endpoints

    def test_all_route_modules_registered(self, app):
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        expected = {
            'login', 'logout', 'dashboard', 'trips', 'fuel',
            'maintenance', 'report', 'vehicles', 'users',
            'delete_vehicle', 'delete_entry',
            'api_add_trip', 'api_add_fuel', 'api_add_maintenance',
            'api_vehicle_last_km', 'api_drivers',
            'logs.logs_list',
        }
        assert expected.issubset(endpoints), f"Missing: {expected - endpoints}"


class TestSecurityHeaders:
    def test_x_content_type_options(self, client):
        response = client.get('/login')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_frame_options(self, client):
        response = client.get('/login')
        assert response.headers.get('X-Frame-Options') == 'DENY'

    def test_x_xss_protection(self, client):
        response = client.get('/login')
        assert response.headers.get('X-XSS-Protection') == '1; mode=block'

    def test_content_security_policy_present(self, client):
        response = client.get('/login')
        csp = response.headers.get('Content-Security-Policy', '')
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_csp_contains_nonce(self, client):
        response = client.get('/login')
        csp = response.headers.get('Content-Security-Policy', '')
        assert 'nonce-' in csp


class TestCSRFProtection:
    def test_post_without_csrf_token_fails(self, client):
        """POST without any CSRF token should fail."""
        response = client.post('/login', data={'username': 'x', 'password': 'y'})
        # Should redirect to login (CSRF failure for non-JSON)
        assert response.status_code == 302

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_post_with_valid_csrf_token_passes(self, mock_get_db, mock_get_cursor, client):
        """POST with matching CSRF token should not be blocked by CSRF check."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # No user found

        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token-123'

        response = client.post('/login', data={
            '_csrf_token': 'test-token-123',
            'username': 'nobody',
            'password': 'wrong',
        })
        # CSRF check passes, but login fails → re-renders login page (200)
        assert response.status_code == 200

    def test_csrf_check_skipped_for_get(self, client):
        """GET requests are not subject to CSRF check."""
        response = client.get('/login')
        assert response.status_code == 200

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_csrf_header_x_csrftoken(self, mock_get_db, mock_get_cursor, client):
        """CSRF token via X-CSRFToken header should work."""
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'header-token'

        response = client.post(
            '/login',
            data={'username': 'x', 'password': 'y'},
            headers={'X-CSRFToken': 'header-token'},
        )
        # Should pass CSRF check (login fails, re-renders page)
        assert response.status_code == 200

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_csrf_header_x_csrf_token(self, mock_get_db, mock_get_cursor, client):
        """CSRF token via X-CSRF-Token header should work."""
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'header-token-2'

        response = client.post(
            '/login',
            data={'username': 'x', 'password': 'y'},
            headers={'X-CSRF-Token': 'header-token-2'},
        )
        assert response.status_code == 200

    @patch('backend.routes.auth.get_cursor')
    @patch('backend.routes.auth.get_db')
    def test_csrf_header_x_xsrf_token(self, mock_get_db, mock_get_cursor, client):
        """CSRF token via X-XSRF-TOKEN header should work."""
        mock_get_db.return_value = MagicMock()
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'xsrf-token'

        response = client.post(
            '/login',
            data={'username': 'x', 'password': 'y'},
            headers={'X-XSRF-TOKEN': 'xsrf-token'},
        )
        assert response.status_code == 200

    def test_mismatched_csrf_in_json_returns_403(self, client):
        """Mismatched CSRF with JSON accept returns 403 JSON."""
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'correct'

        response = client.post(
            '/login',
            data={'_csrf_token': 'wrong'},
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 403
        data = response.get_json()
        assert data['success'] is False
        assert data['code'] == 'csrf_invalid'

    def test_missing_session_csrf_token_fails(self, client):
        """POST with form token but no session token fails."""
        # Don't set any session CSRF token
        response = client.post('/login', data={'_csrf_token': 'some-token'})
        assert response.status_code == 302

    def test_xmlhttprequest_header_triggers_json_csrf_error(self, client):
        """X-Requested-With: XMLHttpRequest triggers JSON CSRF error response."""
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'correct'

        response = client.post(
            '/login',
            data={'_csrf_token': 'wrong'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert response.status_code == 403
        data = response.get_json()
        assert data['code'] == 'csrf_invalid'


class TestValidateRequiredConfig:
    def test_missing_secret_key_in_production_raises(self, monkeypatch):
        """Missing SECRET_KEY in production should raise RuntimeError."""
        monkeypatch.setenv('FLASK_ENV', 'production')

        from backend.config import ProductionConfig

        class BadConfig(ProductionConfig):
            SECRET_KEY = None
            DATABASE_URL = 'postgresql://localhost/test'

        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            create_app(config_class=BadConfig)

    def test_missing_database_url_in_production_raises(self, monkeypatch):
        """Missing DATABASE_URL in production should raise RuntimeError."""
        monkeypatch.setenv('FLASK_ENV', 'production')

        from backend.config import ProductionConfig

        class BadConfig(ProductionConfig):
            SECRET_KEY = 'secret'
            DATABASE_URL = None

        with pytest.raises(RuntimeError, match='DATABASE_URL'):
            create_app(config_class=BadConfig)

    def test_missing_config_in_development_does_not_raise(self, monkeypatch):
        """Missing config in development mode should NOT raise."""
        monkeypatch.setenv('FLASK_ENV', 'development')

        from backend.config import DevelopmentConfig

        class LaxConfig(DevelopmentConfig):
            SECRET_KEY = None
            DATABASE_URL = None

        # Should not raise
        app = create_app(config_class=LaxConfig)
        assert app is not None


class TestContextProcessors:
    def test_csrf_token_generation(self, app):
        """csrf_token() template helper generates and caches token in session."""
        with app.test_request_context():
            session.clear()
            # Get context processors
            ctx = app.jinja_env.globals
            # The context processors are injected per-request, so use test client
        with app.test_client() as c:
            # Make a GET request to trigger context processor
            response = c.get('/login')
            with c.session_transaction() as sess:
                assert '_csrf_token' in sess
                assert len(sess['_csrf_token']) == 64  # token_hex(32) = 64 chars
