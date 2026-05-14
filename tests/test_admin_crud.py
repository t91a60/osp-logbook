"""Tests for admin user management and vehicle management CRUD operations."""

from unittest.mock import patch, MagicMock
import pytest


class TestAdminUserManagement:
    """Tests for the /uzytkownicy POST endpoint (user CRUD)."""

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_add_user_success(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin can add a new user."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'add',
            'username': 'newuser',
            'password': 'strongpassword123',
            'display_name': 'New User',
        })
        assert response.status_code == 302

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_add_user_short_password(self, mock_get_db, mock_get_cursor, admin_client):
        """Short password flashes error and does not insert."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'add',
            'username': 'newuser',
            'password': 'short',
            'display_name': 'New User',
        })
        assert response.status_code == 302
        mock_cur.execute.assert_not_called()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_add_user_duplicate_username(self, mock_get_db, mock_get_cursor, admin_client):
        """Duplicate username flashes error."""
        from psycopg2 import IntegrityError
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.execute.side_effect = IntegrityError('unique violation')
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'add',
            'username': 'existing',
            'password': 'strongpassword123',
            'display_name': 'Existing User',
        })
        assert response.status_code == 302

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_change_password_success(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin can change a user's password."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'change_pw',
            'uid': '2',
            'new_password': 'newstrongpassword',
        })
        assert response.status_code == 302
        mock_conn.commit.assert_called()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_change_password_too_short(self, mock_get_db, mock_get_cursor, admin_client):
        """Short new password flashes error."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'change_pw',
            'uid': '2',
            'new_password': 'short',
        })
        assert response.status_code == 302
        mock_conn.commit.assert_not_called()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_user_success(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin can delete another user."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        # First fetchone: target user exists, not admin
        mock_cur.fetchone.return_value = {'id': 2, 'username': 'other', 'is_admin': False}
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'delete',
            'uid': '2',
        })
        assert response.status_code == 302
        mock_conn.commit.assert_called()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_self_forbidden(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin cannot delete their own account."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']
            uid = sess['user_id']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'delete',
            'uid': str(uid),
        })
        assert response.status_code == 302
        mock_conn.commit.assert_not_called()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_last_admin_forbidden(self, mock_get_db, mock_get_cursor, admin_client):
        """Cannot delete the last admin user."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur

        # Target user is admin, but it's not the current user (uid=2)
        def fetchone_side_effect():
            return fetchone_side_effect.results.pop(0)
        fetchone_side_effect.results = [
            {'id': 2, 'username': 'otheradmin', 'is_admin': True},
            {'count': 0},  # No remaining admins
        ]
        mock_cur.fetchone.side_effect = lambda: fetchone_side_effect()
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'delete',
            'uid': '2',
        })
        assert response.status_code == 302
        mock_conn.commit.assert_not_called()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_nonexistent_user(self, mock_get_db, mock_get_cursor, admin_client):
        """Deleting a nonexistent user flashes error."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # User not found
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'delete',
            'uid': '999',
        })
        assert response.status_code == 302
        mock_conn.commit.assert_not_called()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_invalid_uid(self, mock_get_db, mock_get_cursor, admin_client):
        """Invalid UID (non-integer) flashes error."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'delete',
            'uid': 'abc',
        })
        assert response.status_code == 302

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_no_uid(self, mock_get_db, mock_get_cursor, admin_client):
        """Missing UID flashes error."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/uzytkownicy', data={
            '_csrf_token': csrf,
            'action': 'delete',
        })
        assert response.status_code == 302


class TestAdminVehicleManagement:
    """Tests for the /pojazdy CRUD endpoints."""

    @patch('backend.routes.admin.invalidate_prefix')
    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    @patch('backend.routes.admin.AuditService.log')
    def test_add_vehicle_success(self, mock_audit_log, mock_get_vehicle_repo, mock_invalidate, admin_client):
        """Admin can add a new vehicle."""
        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy', data={
            '_csrf_token': csrf,
            'name': 'Fiat Ducato',
            'plate': 'KR 12345',
            'type': 'GCBA',
        })
        assert response.status_code == 302
        mock_repo.add.assert_called_once()
        mock_invalidate.assert_any_call('vehicles:')
        mock_invalidate.assert_any_call('dashboard:')

    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    def test_list_vehicles(self, mock_get_vehicle_repo, admin_client):
        """Admin can view vehicle list."""
        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.get_all.return_value = [
            {'id': 1, 'name': 'Fiat Ducato', 'plate': 'KR 12345', 'type': 'GCBA'},
        ]

        response = admin_client.get('/pojazdy')
        assert response.status_code == 200

    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    def test_edit_vehicle_get(self, mock_get_vehicle_repo, admin_client):
        """Admin can view vehicle edit form."""
        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.get_by_id.return_value = {
            'id': 1, 'name': 'Old Name', 'plate': 'AB 123', 'type': 'SLRr',
        }

        response = admin_client.get('/pojazdy/1/edytuj')
        assert response.status_code == 200

    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    def test_edit_vehicle_nonexistent(self, mock_get_vehicle_repo, admin_client):
        """Editing nonexistent vehicle redirects with error."""
        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.get_by_id.return_value = None

        response = admin_client.get('/pojazdy/999/edytuj')
        assert response.status_code == 302

    @patch('backend.routes.admin.invalidate_prefix')
    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    @patch('backend.routes.admin.AuditService.log')
    def test_edit_vehicle_post_success(self, mock_audit_log, mock_get_vehicle_repo, mock_invalidate, admin_client):
        """Admin can update a vehicle."""
        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.get_by_id.return_value = {
            'id': 1, 'name': 'Old Name', 'plate': 'AB 123', 'type': 'SLRr',
        }

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/edytuj', data={
            '_csrf_token': csrf,
            'name': 'New Name',
            'plate': 'CD 456',
            'type': 'GCBA',
        })
        assert response.status_code == 302
        mock_repo.update.assert_called_once()
        mock_invalidate.assert_any_call('vehicles:')
        mock_invalidate.assert_any_call('dashboard:')

    @patch('backend.routes.admin.invalidate_prefix')
    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    def test_edit_vehicle_empty_name(self, mock_get_vehicle_repo, mock_invalidate, admin_client):
        """Empty vehicle name shows error."""
        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.get_by_id.return_value = {
            'id': 1, 'name': 'Old Name', 'plate': 'AB 123', 'type': 'SLRr',
        }

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/edytuj', data={
            '_csrf_token': csrf,
            'name': '',
            'plate': 'CD 456',
            'type': 'GCBA',
        })
        # Should re-render the form (not commit)
        mock_repo.update.assert_not_called()

    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    def test_delete_vehicle_with_references(self, mock_get_vehicle_repo, admin_client):
        """Cannot delete vehicle that has trips/fuel/maintenance references."""
        from backend.domain.exceptions import ForbiddenError

        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.delete.side_effect = ForbiddenError('Nie można usunąć pojazdu.')

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/usun', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 302
        mock_repo.delete.assert_called_once_with(1)

    @patch('backend.routes.admin.AuditService.log')
    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    def test_delete_vehicle_success(self, mock_get_vehicle_repo, mock_audit_log, admin_client):
        """Admin can delete a vehicle with no references."""
        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.delete.return_value = None
        mock_audit_log.return_value = None

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/usun', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 302
        mock_repo.delete.assert_called_once_with(1)
        mock_audit_log.assert_called_once()

    @patch('backend.routes.admin.UseCaseFactory.get_vehicle_repo')
    def test_delete_nonexistent_vehicle(self, mock_get_vehicle_repo, admin_client):
        """Deleting a nonexistent vehicle flashes error."""
        from backend.domain.exceptions import NotFoundError

        mock_repo = MagicMock()
        mock_get_vehicle_repo.return_value = mock_repo
        mock_repo.delete.side_effect = NotFoundError('Pojazd nie istnieje.')

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/usun', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 302
        mock_repo.delete.assert_called_once_with(1)
