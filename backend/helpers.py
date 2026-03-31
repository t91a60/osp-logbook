from datetime import date, timedelta
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
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