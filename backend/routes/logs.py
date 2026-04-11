from flask import Blueprint, render_template, request, current_app

from backend.db import get_cursor, get_db
from backend.helpers import admin_required, parse_positive_int

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/logs", endpoint="logs_list")
@admin_required
def logs_list():
    page = parse_positive_int(request.args.get('page'), default=1)

    try:
        page_size = int(current_app.config.get('LOGS_PAGE_SIZE', 50))
    except (TypeError, ValueError):
        page_size = 50
    page_size = page_size if page_size > 0 else 50

    conn = get_db()
    cur = get_cursor(conn)
    try:
        cur.execute('SELECT COUNT(*) AS count FROM audit_log')
        total = cur.fetchone()['count']
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size

        cur.execute("""
            SELECT id, created_at, username, action, object, details
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (page_size, offset))
        logs = cur.fetchall()
    finally:
        cur.close()

    return render_template(
        "logs.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
    )
