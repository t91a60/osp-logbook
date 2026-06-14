"""Tests for backend/services/audit_service.py — AuditService.log()."""

from unittest.mock import MagicMock, patch

import psycopg2


class TestAuditServiceLog:
    """Test AuditService.log() independent transaction behavior."""

    @patch('backend.services.audit_service.get_cursor')
    @patch('backend.services.audit_service.get_pool')
    def test_log_success(self, mock_get_pool, mock_get_cursor):
        """Successful audit log inserts and commits on its own connection."""
        from backend.services.audit_service import AuditService

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        AuditService.log(
            'Dodanie',
            'Wyjazd',
            'Some details',
            user_id=42,
            username='testuser',
        )

        mock_conn.commit.assert_called_once()
        mock_cur.execute.assert_called_once()
        # Verify the INSERT includes user_id and username
        insert_args = mock_cur.execute.call_args[0]
        assert 'INSERT INTO audit_log' in insert_args[0]
        assert insert_args[1] == (42, 'testuser', 'Dodanie', 'Wyjazd', 'Some details')
        # Connection returned to pool
        mock_pool.putconn.assert_called_once()

    @patch('backend.services.audit_service.get_cursor')
    @patch('backend.services.audit_service.get_pool')
    def test_log_with_no_user_context(self, mock_get_pool, mock_get_cursor):
        """Audit log without caller-provided user context uses None values."""
        from backend.services.audit_service import AuditService

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        AuditService.log('Usunięcie', 'Pojazd', 'details')

        insert_args = mock_cur.execute.call_args[0]
        assert insert_args[1][0] is None  # user_id
        assert insert_args[1][1] is None  # username

    @patch('backend.services.audit_service.get_cursor')
    @patch('backend.services.audit_service.get_pool')
    def test_log_db_error_does_not_raise(self, mock_get_pool, mock_get_cursor):
        """psycopg2.Error during audit log is caught and does not propagate."""
        from backend.services.audit_service import AuditService

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = psycopg2.Error('insert failed')

        # Should not raise
        AuditService.log('Dodanie', 'Test', 'details')

        mock_conn.rollback.assert_called_once()
        mock_pool.putconn.assert_called_once()

    @patch('backend.services.audit_service.get_cursor')
    @patch('backend.services.audit_service.get_pool')
    def test_log_uses_independent_connection(self, mock_get_pool, mock_get_cursor):
        """Audit should get its own connection from pool, not from g.db."""
        from backend.services.audit_service import AuditService

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        AuditService.log('Dodanie', 'Test', 'test')

        # Verify pool.getconn() was called (independent connection)
        mock_pool.getconn.assert_called_once()
        # Verify autocommit is set to False
        assert mock_conn.autocommit is False
