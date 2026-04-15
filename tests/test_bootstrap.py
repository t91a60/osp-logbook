"""Tests for backend/bootstrap.py — ensure_bootstrap_admin()."""

from unittest.mock import patch, MagicMock
import psycopg2.errors
import pytest


class TestEnsureBootstrapAdmin:
    """Test the ensure_bootstrap_admin function."""

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_skips_when_no_password(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Should return early when BOOTSTRAP_ADMIN_PASSWORD is not set."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.delenv('BOOTSTRAP_ADMIN_PASSWORD', raising=False)
        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')

        ensure_bootstrap_admin(app)
        mock_get_pool.assert_not_called()

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_skips_when_empty_password(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Empty password should skip bootstrap."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', '  ')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')

        ensure_bootstrap_admin(app)
        mock_get_pool.assert_not_called()

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_skips_when_empty_username(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Empty username should skip bootstrap."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'secret')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', '  ')

        ensure_bootstrap_admin(app)
        mock_get_pool.assert_not_called()

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_creates_new_admin(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Creates new admin user when none exists."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'SecurePass123')
        monkeypatch.delenv('BOOTSTRAP_ADMIN_FORCE_RESET', raising=False)

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = None  # No existing user

        ensure_bootstrap_admin(app)

        # Should INSERT new user
        insert_call = mock_cur.execute.call_args_list[-1]
        assert 'INSERT INTO users' in insert_call[0][0]
        mock_conn.commit.assert_called_once()
        mock_pool.putconn.assert_called_once()

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_skips_existing_admin_without_force_reset(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Existing admin without force_reset should be skipped."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'secret')
        monkeypatch.delenv('BOOTSTRAP_ADMIN_FORCE_RESET', raising=False)

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = {'id': 1}  # Existing user

        ensure_bootstrap_admin(app)

        mock_conn.rollback.assert_called_once()  # Rolled back since no update needed
        mock_conn.commit.assert_not_called()

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_updates_existing_admin_with_force_reset(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Existing admin with FORCE_RESET=1 should be updated."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'NewPass123')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_FORCE_RESET', '1')

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = {'id': 1}  # Existing user

        ensure_bootstrap_admin(app)

        # Should UPDATE existing user
        update_call = mock_cur.execute.call_args_list[-1]
        assert 'UPDATE users' in update_call[0][0]
        mock_conn.commit.assert_called_once()

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_handles_undefined_table_gracefully(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """UndefinedTable error should be caught silently."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'secret')

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.side_effect = psycopg2.errors.UndefinedTable('users table missing')

        # Should not raise
        ensure_bootstrap_admin(app)
        mock_conn.rollback.assert_called()

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_generic_exception_raises(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Non-UndefinedTable exceptions should re-raise."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'secret')

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.side_effect = RuntimeError('unexpected error')

        with pytest.raises(RuntimeError, match='unexpected error'):
            ensure_bootstrap_admin(app)

    @patch('backend.bootstrap.get_cursor')
    @patch('backend.bootstrap.get_pool')
    def test_default_display_name(self, mock_get_pool, mock_get_cursor, app, monkeypatch):
        """Missing DISPLAY_NAME env uses 'Administrator' as default."""
        from backend.bootstrap import ensure_bootstrap_admin

        monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'secret')
        monkeypatch.delenv('BOOTSTRAP_ADMIN_DISPLAY_NAME', raising=False)

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = None

        ensure_bootstrap_admin(app)

        # Verify INSERT was called with 'Administrator' display name
        insert_call = mock_cur.execute.call_args_list[-1]
        assert 'Administrator' in insert_call[0][1]
