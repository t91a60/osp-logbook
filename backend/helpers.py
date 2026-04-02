from datetime import date, timedelta
from contextlib import contextmanager
from functools import wraps
from flask import session, redirect, url_for, abort

from backend.db import get_db, get_cursor


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def require_roles(*allowed_roles):
    normalized = {str(role).strip().lower() for role in allowed_roles}

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            role = str(session.get('role') or 'user').strip().lower()
            if role not in normalized:
                abort(403)
            return f(*args, **kwargs)

        return decorated

    return decorator


def parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None

def build_date_where(okres, od, do_, alias='t'):
    today = date.today()
    parts = []
    params = []

    if okres == 'ten':
        first = today.replace(day=1)
        last = today
        parts.append(f"{alias}.date BETWEEN %s AND %s")
        params += [first, last]
    elif okres == 'poprzedni':
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        parts.append(f"{alias}.date BETWEEN %s AND %s")
        params += [first_prev, last_prev]
    elif od or do_:
        parsed_od = parse_iso_date(od)
        parsed_do = parse_iso_date(do_)

        if parsed_od:
            parts.append(f"{alias}.date >= %s")
            params.append(parsed_od)
        if parsed_do:
            parts.append(f"{alias}.date <= %s")
            params.append(parsed_do)

    return parts, params


def parse_positive_int(value, default=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return parsed if parsed > 0 else default


@contextmanager
def db_tx():
    conn = get_db()
    try:
        with get_cursor(conn) as cur:
            yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
    """Normalize DB date-like values to ISO string (YYYY-MM-DD)."""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def days_since_iso_date(value):
    """Return day difference from today for ISO date-like values."""
    normalized = normalize_iso_date(value)
    if not normalized:
        return None
    try:
        return (date.today() - date.fromisoformat(normalized)).days
    except ValueError:
        return None