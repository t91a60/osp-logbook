from datetime import date, datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, abort


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
        if not session.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def parse_positive_int(value, default=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def normalize_iso_date(value):
    """Normalize different DB date representations to YYYY-MM-DD string."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None

    # Handle values like "YYYY-MM-DD HH:MM:SS" or ISO datetime variants.
    if 'T' in text:
        text = text.split('T', 1)[0]
    elif ' ' in text:
        text = text.split(' ', 1)[0]

    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def days_since_iso_date(value, today=None):
    """Return number of days since a date-like value, or None if invalid."""
    normalized = normalize_iso_date(value)
    if normalized is None:
        return None

    ref = today or date.today()
    try:
        return (ref - date.fromisoformat(normalized)).days
    except ValueError:
        return None


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
    page = max(1, page)
    offset = (page - 1) * page_size

    # Fast path: fetch page data and total rows in one query via window function.
    window_sql = f'''
        SELECT page_rows.*, COUNT(*) OVER() AS __total_count
        FROM ({data_sql}) AS page_rows
        LIMIT %s OFFSET %s
    '''
    cur.execute(window_sql, data_params + [page_size, offset])
    rows = cur.fetchall()

    if rows:
        total = rows[0]['__total_count']
        total_pages = max(1, (total + page_size - 1) // page_size)
        entries = [{k: v for k, v in row.items() if k != '__total_count'} for row in rows]
        return entries, total, total_pages, page

    # Fallback for out-of-range pages while keeping behavior stable.
    cur.execute(count_sql, count_params)
    count_row = cur.fetchone()
    total = count_row[0] if isinstance(count_row, tuple) else count_row['count'] if count_row else 0
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size

    cur.execute(window_sql, data_params + [page_size, offset])
    rows = cur.fetchall()
    entries = [{k: v for k, v in row.items() if k != '__total_count'} for row in rows]
    return entries, total, total_pages, page
