"""Extended tests for backend/db.py."""

from unittest.mock import MagicMock, patch

import psycopg2
from werkzeug.security import generate_password_hash

from backend import db as db_module


class TestCheckDbHealth:
    @patch('backend.db.get_cursor')
    @patch('backend.db.get_db')
    def test_check_db_health_returns_true(self, mock_get_db, mock_get_cursor, app):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur

        with app.test_request_context():
            assert db_module.check_db_health() is True

        mock_cur.execute.assert_called_once_with('SELECT 1')
        mock_cur.close.assert_called_once()

    @patch('backend.db.get_cursor')
    @patch('backend.db.get_db')
    def test_check_db_health_returns_false_on_operational_error(self, mock_get_db, mock_get_cursor, app):
        mock_get_db.return_value = MagicMock()
        mock_get_cursor.side_effect = psycopg2.OperationalError('boom')

        with app.test_request_context():
            assert db_module.check_db_health() is False


class TestGetDb:
    @patch('backend.db.time.sleep')
    @patch('backend.db.reset_pool')
    @patch('backend.db.get_pool')
    def test_get_db_retries_three_times_then_raises(self, mock_get_pool, mock_reset_pool, mock_sleep, app):
        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = psycopg2.OperationalError('db down')
        mock_get_pool.return_value = mock_pool

        with app.test_request_context():
            try:
                db_module.get_db()
            except psycopg2.OperationalError:
                pass
            else:
                raise AssertionError('OperationalError not raised')

        assert mock_pool.getconn.call_count == 3
        assert mock_sleep.call_count == 2
        assert mock_reset_pool.call_count == 3


class TestCloseDb:
    @patch.object(db_module, '_db_pool', new=None)
    def test_close_db_returns_connection_to_pool(self, app):
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool = MagicMock()
        with patch('backend.db._db_pool', mock_pool):
            with app.test_request_context():
                from flask import g

                g.db = mock_conn
                db_module.close_db(None)

        mock_pool.putconn.assert_called_once_with(mock_conn, close=False)


class TestInitDb:
    @patch('backend.db.get_cursor')
    @patch('backend.db.get_pool')
    @patch('backend.db._fetch_schema_version')
    def test_init_db_raises_when_users_table_missing(self, mock_schema_version, mock_get_pool, mock_get_cursor, monkeypatch):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [{'exists': False}]
        mock_get_cursor.return_value = mock_cur

        monkeypatch.delenv('BOOTSTRAP_ADMIN_PASSWORD', raising=False)

        try:
            db_module.init_db()
        except RuntimeError as exc:
            assert 'schema.sql' in str(exc)
        else:
            raise AssertionError('RuntimeError not raised')

        mock_conn.rollback.assert_called_once()
        mock_schema_version.assert_not_called()

    @patch('backend.db.get_cursor')
    @patch('backend.db.get_pool')
    @patch('backend.db._fetch_schema_version')
    def test_init_db_skips_password_update_for_real_hash(self, mock_schema_version, mock_get_pool, mock_get_cursor, monkeypatch):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            {'exists': True},
            {'id': 1, 'password': generate_password_hash('real-password')},
        ]
        mock_get_cursor.return_value = mock_cur
        mock_schema_version.return_value = 1

        monkeypatch.delenv('BOOTSTRAP_ADMIN_PASSWORD', raising=False)

        db_module.init_db()

        executed_sql = ' '.join(call.args[0] for call in mock_cur.execute.call_args_list)
        assert 'UPDATE users' not in executed_sql
        assert 'INSERT INTO users' not in executed_sql
        mock_conn.commit.assert_called_once()
"""Extended tests for backend/db.py — get_db retries, close_db pool return, init_db paths."""

import os
from unittest.mock import patch, MagicMock, PropertyMock
import pytest
import psycopg2

from backend import db as db_module


class TestGetDbRetries:
    """get_db() retries up to 3 times on OperationalError then raises."""

    @patch('backend.db.reset_pool')
    @patch('backend.db.get_pool')
    def test_retries_three_times_then_raises(self, mock_get_pool, mock_reset, app):
        pool = MagicMock()
        pool.getconn.side_effect = psycopg2.OperationalError('connection refused')
        mock_get_pool.return_value = pool

        with app.test_request_context():
            from flask import g
            g.pop('db', None)
            with pytest.raises(psycopg2.OperationalError):
                db_module.get_db()

            assert pool.getconn.call_count == 3
            assert mock_reset.call_count == 3

    @patch('backend.db.get_pool')
    def test_returns_conn_on_first_success(self, mock_get_pool, app):
        pool = MagicMock()
        mock_conn = MagicMock()
        pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = pool

        with app.test_request_context():
            from flask import g
            g.pop('db', None)
            conn = db_module.get_db()

        assert conn is mock_conn
        assert mock_conn.autocommit is False
        assert pool.getconn.call_count == 1

    @patch('backend.db.reset_pool')
    @patch('backend.db.get_pool')
    def test_retries_then_succeeds(self, mock_get_pool, mock_reset, app):
        pool = MagicMock()
        mock_conn = MagicMock()
        pool.getconn.side_effect = [
            psycopg2.OperationalError('fail 1'),
            mock_conn,
        ]
        mock_get_pool.return_value = pool

        with app.test_request_context():
            from flask import g
            g.pop('db', None)
            conn = db_module.get_db()

        assert conn is mock_conn
        assert pool.getconn.call_count == 2


class TestCloseDbPoolReturn:
    """close_db() returns connection to pool."""

    def test_close_db_returns_conn_to_pool(self, app):
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool = MagicMock()

        with app.test_request_context():
            from flask import g
            g.db = mock_conn
            with patch.object(db_module, '_db_pool', mock_pool):
                db_module.close_db(None)

        mock_conn.rollback.assert_called_once()
        mock_pool.putconn.assert_called_once()

    def test_close_db_handles_closed_connection(self, app):
        mock_conn = MagicMock()
        mock_conn.closed = True
        mock_pool = MagicMock()

        with app.test_request_context():
            from flask import g
            g.db = mock_conn
            with patch.object(db_module, '_db_pool', mock_pool):
                db_module.close_db(None)

        mock_pool.putconn.assert_called_once_with(mock_conn, close=True)


class TestInitDb:
    """init_db() schema validation and admin setup paths."""

    @patch('backend.db.get_pool')
    def test_raises_when_users_table_missing(self, mock_get_pool):
        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        pool.getconn.return_value = mock_conn

        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = {'exists': False}
        mock_conn.cursor.return_value = mock_cur

        mock_get_pool.return_value = pool

        with pytest.raises(RuntimeError, match='schema.sql'):
            db_module.init_db()

        mock_conn.rollback.assert_called()

    @patch('backend.db._fetch_schema_version', return_value=1)
    @patch('backend.db.get_pool')
    def test_skips_password_update_when_admin_has_real_hash(self, mock_get_pool, mock_sv):
        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        pool.getconn.return_value = mock_conn

        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        # First call: check users table exists; second: fetch admin row
        mock_cur.fetchone.side_effect = [
            {'exists': True},
            {'id': 1, 'password': 'scrypt:32768:8:1$real_hash_here'},
        ]
        mock_conn.cursor.return_value = mock_cur

        mock_get_pool.return_value = pool

        db_module.init_db()

        # admin already has real hash — no INSERT or UPDATE should happen
        mock_conn.commit.assert_called_once()
        # The cursor should NOT have executed an INSERT or UPDATE for the admin password
        for call in mock_cur.execute.call_args_list:
            sql_text = call.args[0] if call.args else ''
            assert 'INSERT INTO users' not in sql_text
            assert 'UPDATE users' not in sql_text

    @patch('backend.db._fetch_schema_version', return_value=1)
    @patch('backend.db.get_pool')
    def test_updates_placeholder_password(self, mock_get_pool, mock_sv, monkeypatch):
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'NewSecurePass123')

        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        pool.getconn.return_value = mock_conn

        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.side_effect = [
            {'exists': True},
            {'id': 1, 'password': db_module.ADMIN_PLACEHOLDER_PASSWORD},
        ]
        mock_conn.cursor.return_value = mock_cur

        mock_get_pool.return_value = pool

        db_module.init_db()

        mock_conn.commit.assert_called_once()
        # Should have executed an UPDATE for the admin password
        update_calls = [
            c for c in mock_cur.execute.call_args_list
            if c.args and 'UPDATE users' in c.args[0]
        ]
        assert len(update_calls) == 1

    @patch('backend.db.get_pool')
    def test_raises_when_no_admin_and_no_env_password(self, mock_get_pool, monkeypatch):
        monkeypatch.delenv('BOOTSTRAP_ADMIN_PASSWORD', raising=False)

        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        pool.getconn.return_value = mock_conn

        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.side_effect = [
            {'exists': True},
            None,  # no admin row
        ]
        mock_conn.cursor.return_value = mock_cur

        mock_get_pool.return_value = pool

        with pytest.raises(RuntimeError, match='BOOTSTRAP_ADMIN_PASSWORD'):
            db_module.init_db()


class TestCheckDbHealthExtended:
    """Additional edge cases for check_db_health()."""

    @patch('backend.db.get_db')
    def test_returns_false_on_operational_error(self, mock_get_db, app):
        mock_get_db.side_effect = psycopg2.OperationalError('down')

        with app.test_request_context():
            result = db_module.check_db_health()

        assert result is False
