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
    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_add_vehicle_success(self, mock_get_db, mock_get_cursor, mock_invalidate, admin_client):
        """Admin can add a new vehicle."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy', data={
            '_csrf_token': csrf,
            'name': 'Fiat Ducato',
            'plate': 'KR 12345',
            'type': 'GCBA',
        })
        assert response.status_code == 302
        mock_conn.commit.assert_called()
        mock_invalidate.assert_called_with('vehicles:')

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_list_vehicles(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin can view vehicle list."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {'id': 1, 'name': 'Fiat Ducato', 'plate': 'KR 12345', 'type': 'GCBA'},
        ]

        response = admin_client.get('/pojazdy')
        assert response.status_code == 200

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_edit_vehicle_get(self, mock_get_db, mock_get_cursor, admin_client):
        """Admin can view vehicle edit form."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 1, 'name': 'Old Name', 'plate': 'AB 123', 'type': 'SLRr',
        }

        response = admin_client.get('/pojazdy/1/edytuj')
        assert response.status_code == 200

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_edit_vehicle_nonexistent(self, mock_get_db, mock_get_cursor, admin_client):
        """Editing nonexistent vehicle redirects with error."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        response = admin_client.get('/pojazdy/999/edytuj')
        assert response.status_code == 302

    @patch('backend.routes.admin.invalidate_prefix')
    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_edit_vehicle_post_success(self, mock_get_db, mock_get_cursor, mock_invalidate, admin_client):
        """Admin can update a vehicle."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
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
        mock_conn.commit.assert_called()
        mock_invalidate.assert_called_with('vehicles:')

    @patch('backend.routes.admin.invalidate_prefix')
    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_edit_vehicle_empty_name(self, mock_get_db, mock_get_cursor, mock_invalidate, admin_client):
        """Empty vehicle name shows error."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
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
        mock_conn.commit.assert_not_called()

    @patch('backend.routes.admin.VehicleService')
    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_vehicle_with_references(self, mock_get_db, mock_get_cursor, mock_vehicle_svc, admin_client):
        """Cannot delete vehicle that has trips/fuel/maintenance references."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.side_effect = [
            {'id': 1},        # Vehicle exists
            {'count': 5},     # Has 5 references
        ]

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/usun', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 302
        mock_vehicle_svc.delete_vehicle.assert_not_called()

    @patch('backend.routes.admin.VehicleService')
    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_vehicle_success(self, mock_get_db, mock_get_cursor, mock_vehicle_svc, admin_client):
        """Admin can delete a vehicle with no references."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.side_effect = [
            {'id': 1},        # Vehicle exists
            {'count': 0},     # No references
        ]

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/usun', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 302
        mock_vehicle_svc.delete_vehicle.assert_called_once()

    @patch('backend.routes.admin.get_cursor')
    @patch('backend.routes.admin.get_db')
    def test_delete_nonexistent_vehicle(self, mock_get_db, mock_get_cursor, admin_client):
        """Deleting a nonexistent vehicle flashes error."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_cur = MagicMock()
        mock_get_cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None  # Vehicle not found

        with admin_client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        response = admin_client.post('/pojazdy/1/usun', data={
            '_csrf_token': csrf,
        })
        assert response.status_code == 302
