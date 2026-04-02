from flask import Blueprint, render_template

from backend.db import get_cursor, get_db
from backend.helpers import login_required

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/logs", endpoint="logs_list")
@login_required
def logs_list():
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
