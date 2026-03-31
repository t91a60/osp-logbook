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
    total = cur.fetchone()[0]
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    cur.execute(
        data_sql + " LIMIT %s OFFSET %s", data_params + [page_size, offset]
    )
    entries = cur.fetchall()
    return entries, total, total_pages, page