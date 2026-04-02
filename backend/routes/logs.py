from flask import Blueprint, render_template, abort, session

from backend.db import get_cursor, get_db
from backend.helpers import login_required

logs_bp = Blueprint("logs", __name__)


def _is_admin() -> bool:
    role = str(session.get('role') or '').strip().lower()
    if role == 'admin':
        return True

    uid = session.get('user_id')
    username = str(session.get('username') or '').strip().lower()
    if not uid:
        return False

    conn = get_db()
    with get_cursor(conn) as cur:
        cur.execute('SELECT role FROM users WHERE id = %s', (uid,))
        row = cur.fetchone()

    refreshed_role = str((row or {}).get('role') or 'user').strip().lower()
    if refreshed_role != 'admin' and username == 'admin':
        with get_cursor(conn) as cur:
            cur.execute("UPDATE users SET role = 'admin' WHERE id = %s", (uid,))
        conn.commit()
        refreshed_role = 'admin'

    session['role'] = refreshed_role or 'user'
    return session['role'] == 'admin'


@logs_bp.route("/logs", endpoint="logs_list")
@login_required
def logs_list():
    if not _is_admin():
        abort(403)

    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("""
        SELECT id, created_at, username, action, object, details
        FROM audit_log
        ORDER BY created_at DESC
    """)
    logs = cur.fetchall()
    cur.close()
    return render_template("logs.html", logs=logs)
