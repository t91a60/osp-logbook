"""Shared test fixtures for the OSP Logbook test suite."""

import os
import pytest

# NOTE: These tests mock get_db() and get_cursor() — they verify routing
# logic and input validation but do NOT execute real SQL queries.
# For SQL and migration correctness, run integration tests against a
# real PostgreSQL instance:
#   docker run -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:17
#   DATABASE_URL=postgresql://postgres:test@localhost/test pytest tests/integration/

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


# ---------------------------------------------------------------------------
# Mock repository fixtures for application-layer unit tests
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock


@pytest.fixture
def mock_trip_repo():
    repo = MagicMock()
    repo.add.return_value = 1
    repo.get_page.return_value = ([], 0, 1, 1)
    return repo


@pytest.fixture
def mock_vehicle_repo():
    repo = MagicMock()
    repo.get_active.return_value = {'id': 1, 'name': 'Fiat Ducato', 'plate': 'SBI 001'}
    return repo


@pytest.fixture
def mock_fuel_repo():
    repo = MagicMock()
    repo.add.return_value = None
    repo.get_by_id.return_value = {
        'id': 1, 'vehicle_id': 1, 'date': '2026-05-01',
        'driver': 'Jan', 'liters': 40.0, 'added_by': 'jan'
    }
    return repo


@pytest.fixture
def mock_maintenance_repo():
    repo = MagicMock()
    repo.add.return_value = None
    repo.complete.return_value = {'id': 1, 'status': 'completed', 'added_by': 'jan'}
    repo.create_next.return_value = {'id': 2, 'status': 'pending', 'added_by': 'jan'}
    return repo


@pytest.fixture
def mock_dashboard_repo():
    repo = MagicMock()
    repo.get_vehicle_cards.return_value = [
        {'id': 1, 'name': 'Fiat Ducato', 'plate': 'SBI 001',
         'type': 'GBA', 'last_km': 37500, 'last_trip_date': '2026-05-01'}
    ]
    repo.get_recent_trips.return_value = []
    repo.get_recent_fuel.return_value = []
    repo.get_aggregate_stats.return_value = {'trips': 10, 'fuel': 5, 'maintenance': 2}
    return repo
