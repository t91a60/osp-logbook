"""Tests for backend/db.py — database utilities, health check, retry logic."""

from unittest.mock import patch, MagicMock
import pytest
import psycopg2

from backend import db as db_module


class TestCheckDbHealth:
    """Test check_db_health() success and failure paths."""

    @patch('backend.db.get_cursor')
    @patch('backend.db.get_db')
    def test_healthy_db_returns_true(self, mock_get_db, mock_get_cursor, app):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur

        with app.test_request_context():
            result = db_module.check_db_health()

        assert result is True
        mock_cur.execute.assert_called_once_with("SELECT 1")
        mock_cur.close.assert_called_once()

    @patch('backend.db.get_cursor')
    @patch('backend.db.get_db')
    def test_unhealthy_db_returns_false(self, mock_get_db, mock_get_cursor, app):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_get_cursor.side_effect = Exception("Connection refused")

        with app.test_request_context():
            result = db_module.check_db_health()

        assert result is False

    @patch('backend.db.get_cursor')
    @patch('backend.db.get_db')
    def test_query_failure_returns_false(self, mock_get_db, mock_get_cursor, app):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.execute.side_effect = psycopg2.OperationalError("timeout")

        with app.test_request_context():
            result = db_module.check_db_health()

        assert result is False


class TestRetryOnConnectionFailure:
    """Test _retry_on_connection_failure decorator logic."""

    def test_succeeds_first_try(self, app):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            return 'ok'

        with app.test_request_context():
            result = db_module._retry_on_connection_failure(fn, max_retries=3, delay=0)

        assert result == 'ok'
        assert call_count == 1

    @patch('backend.db.reset_pool')
    @patch('backend.db.get_pool')
    @patch('backend.db.time')
    def test_retries_on_operational_error(self, mock_time, mock_get_pool, mock_reset_pool, app):
        mock_time.sleep = MagicMock()
        mock_pool = MagicMock()
        mock_get_pool.return_value = mock_pool
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise psycopg2.OperationalError("connection reset")
            return 'recovered'

        with app.test_request_context():
            result = db_module._retry_on_connection_failure(fn, max_retries=3, delay=0)

        assert result == 'recovered'
        assert call_count == 3

    @patch('backend.db.reset_pool')
    @patch('backend.db.get_pool')
    @patch('backend.db.time')
    def test_raises_after_max_retries(self, mock_time, mock_get_pool, mock_reset_pool, app):
        mock_time.sleep = MagicMock()
        mock_get_pool.return_value = MagicMock()

        def fn():
            raise psycopg2.OperationalError("permanently down")

        with app.test_request_context():
            with pytest.raises(psycopg2.OperationalError, match="permanently down"):
                db_module._retry_on_connection_failure(fn, max_retries=2, delay=0)

    @patch('backend.db.reset_pool')
    @patch('backend.db.get_pool')
    @patch('backend.db.time')
    def test_retries_on_interface_error(self, mock_time, mock_get_pool, mock_reset_pool, app):
        mock_time.sleep = MagicMock()
        mock_pool = MagicMock()
        mock_get_pool.return_value = mock_pool
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise psycopg2.InterfaceError("connection closed")
            return 'ok'

        with app.test_request_context():
            result = db_module._retry_on_connection_failure(fn, max_retries=3, delay=0)

        assert result == 'ok'
        assert call_count == 2

    def test_max_retries_less_than_one_raises_value_error(self, app):
        with pytest.raises(ValueError, match="max_retries must be >= 1"):
            db_module._retry_on_connection_failure(lambda: None, max_retries=0)


class TestGetCursor:
    """Test get_cursor returns a RealDictCursor."""

    def test_returns_cursor_with_factory(self):
        mock_conn = MagicMock()
        db_module.get_cursor(mock_conn)
        mock_conn.cursor.assert_called_once_with(cursor_factory=psycopg2.extras.RealDictCursor)


class TestCloseDb:
    """Test close_db teardown function."""

    def test_close_db_with_no_connection(self, app):
        """close_db is safe to call when no db in g."""
        with app.test_request_context():
            db_module.close_db(None)  # Should not raise

    @patch.object(db_module, '_db_pool', new=None)
    def test_close_db_without_pool_closes_connection(self, app):
        """If pool is None, connection is closed directly."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        with app.test_request_context():
            from flask import g
            g.db = mock_conn
            db_module.close_db(None)
        mock_conn.close.assert_called()


class TestCreatePool:
    """Test _create_pool configuration."""

    @patch('backend.db.SimpleConnectionPool')
    def test_pool_creation_with_defaults(self, mock_pool_cls, monkeypatch):
        monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/test')
        monkeypatch.delenv('DB_POOL_MIN', raising=False)
        monkeypatch.delenv('DB_POOL_MAX', raising=False)
        db_module._create_pool()
        mock_pool_cls.assert_called_once()
        call_kwargs = mock_pool_cls.call_args[1]
        assert call_kwargs['minconn'] == 1
        assert call_kwargs['maxconn'] == 10

    @patch('backend.db.SimpleConnectionPool')
    def test_pool_maxconn_clamped_to_minconn(self, mock_pool_cls, monkeypatch):
        """If maxconn < minconn, maxconn is adjusted."""
        monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/test')
        monkeypatch.setenv('DB_POOL_MIN', '5')
        monkeypatch.setenv('DB_POOL_MAX', '2')
        db_module._create_pool()
        call_kwargs = mock_pool_cls.call_args[1]
        assert call_kwargs['maxconn'] >= call_kwargs['minconn']
