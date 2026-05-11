from datetime import date, datetime, timedelta
from functools import wraps
from collections.abc import Callable
import re

from flask import session, redirect, url_for, abort


def login_required[**P, R](f: Callable[P, R]) -> Callable[P, R]:
    @wraps(f)
    def decorated(*args: P.args, **kwargs: P.kwargs) -> R:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required[**P, R](f: Callable[P, R]) -> Callable[P, R]:
    """Wymaga zalogowania ORAZ flagi is_admin w sesji."""
    @wraps(f)
    def decorated(*args: P.args, **kwargs: P.kwargs) -> R:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def parse_positive_int(value: str | int | None, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def parse_trip_equipment_form(form) -> list[dict]:
    """Parse and validate trip equipment rows from submitted form data.

    Expects parallel arrays: ``eq_id[]``, ``eq_qty[]``, ``eq_min[]``.
    Returns normalized rows for TripRepository in shape:
    ``{'equipment_id': int, 'quantity_used': int, 'minutes_used': int}``.
    Raises ``ValueError`` with user-facing validation messages on invalid input.
    """
    eq_ids = form.getlist('eq_id[]')
    eq_qtys = form.getlist('eq_qty[]')
    eq_mins = form.getlist('eq_min[]')
    max_len = max(len(eq_ids), len(eq_qtys), len(eq_mins), 0)

    equipment_used = []
    for i in range(max_len):
        eq_id_raw = (eq_ids[i] if i < len(eq_ids) else '').strip()
        eq_qty_raw = (eq_qtys[i] if i < len(eq_qtys) else '').strip()
        eq_min_raw = (eq_mins[i] if i < len(eq_mins) else '').strip()

        if not (eq_id_raw or eq_qty_raw or eq_min_raw):
            continue

        try:
            eq_id = int(eq_id_raw)
        except (TypeError, ValueError):
            raise ValueError('Wybierz poprawny sprzęt.')
        if eq_id <= 0:
            raise ValueError('Wybierz poprawny sprzęt.')

        if not eq_min_raw:
            raise ValueError('Podaj czas użycia sprzętu (minuty).')
        try:
            eq_min = int(eq_min_raw)
        except (TypeError, ValueError):
            raise ValueError('Czas użycia sprzętu musi być liczbą całkowitą.')
        if eq_min <= 0:
            raise ValueError('Czas użycia sprzętu musi być większy od 0.')

        eq_qty = 1
        if eq_qty_raw:
            try:
                eq_qty = int(eq_qty_raw)
            except (TypeError, ValueError):
                raise ValueError('Ilość sprzętu musi być liczbą całkowitą.')
            if eq_qty <= 0:
                raise ValueError('Ilość sprzętu musi być większa od 0.')

        equipment_used.append({
            'equipment_id': eq_id,
            'quantity_used': eq_qty,
            'minutes_used': eq_min,
        })

    return equipment_used


def normalize_iso_date(value: str | date | datetime | None) -> str | None:
    """Normalize different DB date representations to YYYY-MM-DD string."""
    match value:
        case None | '':
            return None
        case datetime() as dt:
            return dt.date().isoformat()
        case date() as d:
            return d.isoformat()
        case _:
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


def days_since_iso_date(value: str | date | datetime | None, today: date | None = None) -> int | None:
    """Return number of days since a date-like value, or None if invalid."""
    normalized = normalize_iso_date(value)
    if normalized is None:
        return None

    ref = today or date.today()
    try:
        return (ref - date.fromisoformat(normalized)).days
    except ValueError:
        return None


def build_date_where(
    okres: str | None,
    od: str | None,
    do_: str | None,
    alias: str = 't',
) -> tuple[list[str], list[str]]:
    today = date.today()
    parts: list[str] = []
    params: list[str] = []

    match okres:
        case 'ten':
            first = today.replace(day=1).isoformat()
            last = today.isoformat()
            parts.append(f"{alias}.date BETWEEN %s AND %s")
            params += [first, last]
        case 'poprzedni':
            first_this = today.replace(day=1)
            last_prev = (first_this - timedelta(days=1)).isoformat()
            first_prev = (first_this - timedelta(days=1)).replace(day=1).isoformat()
            parts.append(f"{alias}.date BETWEEN %s AND %s")
            params += [first_prev, last_prev]
        case _:
            if od or do_:
                if od:
                    parts.append(f"{alias}.date >= %s")
                    params.append(od)
                if do_:
                    parts.append(f"{alias}.date <= %s")
                    params.append(do_)

    return parts, params


def paginate(
    conn,
    cur,
    count_sql: str,
    count_params: list,
    data_sql: str,
    data_params: list,
    page: int,
    page_size: int = 50,
) -> tuple[list[dict], int, int, int]:
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


_ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def ensure_non_empty_text(value: str | None, field_name: str) -> str:
    text = (value or '').strip()
    if not text:
        raise ValueError(f'{field_name} jest wymagany.')
    return text


def validate_iso_date(
    value: str | None,
    field_name: str = 'Data',
    max_future_days: int = 365,
) -> str:
    text = (value or '').strip()
    if not text:
        raise ValueError(f'{field_name} jest wymagana.')
    if not _ISO_DATE_RE.fullmatch(text):
        raise ValueError(f'{field_name} musi mieć format YYYY-MM-DD.')

    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise ValueError(f'{field_name} musi mieć format YYYY-MM-DD.')

    if parsed > date.today() + timedelta(days=max_future_days):
        raise ValueError(f'{field_name} nie może być zbyt odległa w przyszłości.')
    return parsed.isoformat()


def parse_positive_int_field(value: str | int | None, field_name: str) -> int | None:
    if value in (None, ''):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} musi być liczbą całkowitą.')
    if parsed <= 0:
        raise ValueError(f'{field_name} musi być większy od 0.')
    return parsed


def parse_positive_float_field(value: str | float | None, field_name: str) -> float | None:
    if value in (None, ''):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} musi być liczbą.')
    if parsed <= 0:
        raise ValueError(f'{field_name} musi być większy od 0.')
    return parsed


def require_float_field(value: str | float | None, field_name: str) -> float | None:
    """Like ``parse_positive_float_field`` but raises ``ValidationError`` instead of ``ValueError``.

    Intended for use in route handlers that map ``ValidationError`` → HTTP 422.
    """
    from backend.domain.exceptions import ValidationError  # local import avoids circular dep
    try:
        return parse_positive_float_field(value, field_name)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def require_int_field(value: str | int | None, field_name: str) -> int | None:
    """Like ``parse_positive_int_field`` but raises ``ValidationError`` instead of ``ValueError``.

    Intended for use in route handlers that map ``ValidationError`` → HTTP 422.
    """
    from backend.domain.exceptions import ValidationError  # local import avoids circular dep
    try:
        return parse_positive_int_field(value, field_name)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def validate_odometer_range(
    odo_start: int | None,
    odo_end: int | None,
) -> None:
    if odo_start is not None and odo_end is not None and odo_end < odo_start:
        raise ValueError('Km koniec nie może być mniejszy niż km start.')
