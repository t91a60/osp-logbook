from datetime import date, datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, abort
from backend.db import get_db, get_cursor


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Wymaga zalogowania ORAZ flagi is_admin w sesji."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # Treat session as cache only; verify from DB when flag is missing/false.
        if not session.get('is_admin'):
            conn = get_db()
            cur = get_cursor(conn)
            try:
                cur.execute('SELECT is_admin FROM users WHERE id = %s', (session.get('user_id'),))
                row = cur.fetchone()
            finally:
                cur.close()

            if not row or not bool(row['is_admin']):
                abort(403)

            # Sync session so next checks are fast.
            session['is_admin'] = True

        return f(*args, **kwargs)
    return decorated


def build_date_where(okres, od, do_, alias='t'):
    today = date.today()
    parts = []
    params = []

    if okres == 'ten':
        first = today.replace(day=1).isoformat()
        last = today.isoformat()
        parts.append(f"{alias}.date BETWEEN %s AND %s")
        params += [first, last]
    elif okres == 'poprzedni':
        first_this = today.replace(day=1)
        last_prev = (first_this - timedelta(days=1)).isoformat()
        first_prev = (first_this - timedelta(days=1)).replace(day=1).isoformat()
        parts.append(f"{alias}.date BETWEEN %s AND %s")
        params += [first_prev, last_prev]
    elif od or do_:
        if od:
            parts.append(f"{alias}.date >= %s")
            params.append(od)
        if do_:
            parts.append(f"{alias}.date <= %s")
            params.append(do_)

    return parts, params


def paginate(conn, cur, count_sql, count_params, data_sql, data_params, page, page_size=50):
    cur.execute(count_sql, count_params)
    row = cur.fetchone()
    total = row[0] if isinstance(row, tuple) else row['count'] if row else 0
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    cur.execute(
        data_sql + " LIMIT %s OFFSET %s", data_params + [page_size, offset]
    )
    entries = cur.fetchall()
    return entries, total, total_pages, page


def normalize_iso_date(value):
    if value in (None, ''):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)


def days_since_iso_date(value, today=None):
    normalized = normalize_iso_date(value)
    if not normalized:
        return None
    if today is None:
        today = date.today()
    return (today - date.fromisoformat(normalized)).days
