"""Shared test fixtures for the OSP Logbook test suite."""

import os
import pytest

# Ensure test environment is set before importing the app.
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
os.environ.setdefault('DATABASE_URL', 'postgresql://localhost/osp_test')

from app import create_app
from backend.config import DevelopmentConfig


class TestConfig(DevelopmentConfig):
    """Configuration used exclusively by the test suite."""
    TESTING = True
    SECRET_KEY = 'test-secret-key-for-testing'
    DATABASE_URL = 'postgresql://localhost/osp_test'
    SERVER_NAME = 'localhost'
    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False


@pytest.fixture()
def app():
    """Create a fresh Flask app for each test."""
    application = create_app(config_class=TestConfig)
    application.config['RATELIMIT_ENABLED'] = False
    yield application


@pytest.fixture()
def client(app):
    """Test client that can make HTTP requests."""
    return app.test_client()


@pytest.fixture()
def app_context(app):
    """Push an application context for the duration of the test."""
    with app.app_context():
        yield app


@pytest.fixture()
def request_context(app):
    """Push a request context for the duration of the test."""
    with app.test_request_context():
        yield app


@pytest.fixture()
def authenticated_client(client):
    """Test client with an authenticated user session."""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'testuser'
        sess['display_name'] = 'Test User'
        sess['is_admin'] = False
        sess['_csrf_token'] = 'valid-csrf-token'
    return client


@pytest.fixture()
def admin_client(client):
    """Test client with an authenticated admin session."""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'admin'
        sess['display_name'] = 'Admin User'
        sess['is_admin'] = True
        sess['_csrf_token'] = 'valid-csrf-token'
    return client
