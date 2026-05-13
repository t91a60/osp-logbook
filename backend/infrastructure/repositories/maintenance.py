from __future__ import annotations

from datetime import date, timedelta

from backend.db import get_db, get_cursor
from backend.services.cache_service import invalidate_prefix
from backend.helpers import build_date_where, normalize_iso_date, paginate, parse_positive_int
from backend.infrastructure.repositories import _to_int, _to_float
from backend.domain.exceptions import ForbiddenError, NotFoundError


class MaintenanceRepository:
    def add(
        self,
        vehicle_id: int | str | None,
        date_val: str,
        odometer: int | str | None,
        description: str,
        cost: float | str | None,
        notes: str,
        added_by: str,
        status: str,
        priority: str,
        due_date: str | None,
    ) -> None:
        conn = get_db()
        vehicle_id = _to_int(vehicle_id)
        odometer = _to_int(odometer)
        cost = _to_float(cost)

        try:
            with get_cursor(conn) as cur:
                cur.execute('''
                        INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (vehicle_id, date_val, odometer, description, cost, notes, added_by, status, priority, due_date))
                conn.commit()
                # Invalidate dashboard snapshot and last-km cache so UIs refresh immediately
                try:
                    invalidate_prefix('dashboard:')
                    invalidate_prefix(f'api:last_km:{vehicle_id}')
                except Exception:
                    pass
        except Exception:
            conn.rollback()
            raise

    def get_by_id(self, entry_id: int | str) -> dict | None:
        """Return a single maintenance row by primary key (with vname JOIN), or None."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute(
                """
                SELECT m.*,
                       v.name AS vname,
                       CASE
                           WHEN m.status = 'completed' THEN 'completed'
                           WHEN m.due_date IS NOT NULL AND m.due_date < CURRENT_DATE THEN 'overdue'
                           ELSE 'pending'
                       END AS effective_status
                FROM maintenance m
                JOIN vehicles v ON m.vehicle_id = v.id
                WHERE m.id = %s
                LIMIT 1
                """,
                (entry_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()

    def update(
        self,
        entry_id: int | str,
        vehicle_id: int | str | None,
        date_val: str,
        odometer: int | str | None,
        description: str,
        cost: float | str | None,
        notes: str,
        status: str,
        priority: str,
        due_date: str | None,
    ) -> None:
        """Update all mutable fields of a maintenance entry. Raises NotFoundError if missing."""
        conn = get_db()
        vehicle_id = _to_int(vehicle_id)
        odometer = _to_int(odometer)
        cost = _to_float(cost)

        try:
            with get_cursor(conn) as cur:
                cur.execute(
                    """
                    UPDATE maintenance
                    SET vehicle_id  = %s,
                        date        = %s,
                        odometer    = %s,
                        description = %s,
                        cost        = %s,
                        notes       = %s,
                        status      = %s,
                        priority    = %s,
                        due_date    = %s
                    WHERE id = %s
                    """,
                    (
                        vehicle_id, date_val, odometer, description,
                        cost, notes, status, priority, due_date, entry_id,
                    ),
                )
                if cur.rowcount == 0:
                    raise NotFoundError('Wpis serwisowy nie istnieje.')
            conn.commit()
            try:
                invalidate_prefix('dashboard:')
                invalidate_prefix(f'api:last_km:{vehicle_id}')
            except Exception:
                pass
        except Exception:
            conn.rollback()
            raise

    def delete(
        self,
        entry_id: int | str,
        requester: str,
        *,
        is_admin: bool = False,
    ) -> None:
        """Delete a maintenance entry.

        Raises:
            NotFoundError: when the entry does not exist.
            ForbiddenError: when the requester is neither the author nor an admin.
        """
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute(
                'SELECT id, added_by, vehicle_id FROM maintenance WHERE id = %s LIMIT 1',
                (entry_id,),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError('Wpis serwisowy nie istnieje.')
            if not is_admin and row.get('added_by') != requester:
                raise ForbiddenError('Brak uprawnień do usunięcia wpisu serwisowego.')

            vid = row.get('vehicle_id')
            cur.execute('DELETE FROM maintenance WHERE id = %s', (entry_id,))
            conn.commit()
            try:
                invalidate_prefix('dashboard:')
                invalidate_prefix(f'api:last_km:{vid}')
            except Exception:
                pass
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def get_page(
        self,
        *,
        vehicle_id: str | int | None = None,
        status_filter: str = 'all',
        okres: str = '',
        od: str = '',
        do_: str = '',
        page: int = 1,
    ) -> tuple[list[dict], int, int, int]:
        conn = get_db()
        cur = get_cursor(conn)
        try:
            page = parse_positive_int(page, default=1)
            where_parts = []
            params = []

            if vehicle_id and vehicle_id != 'all':
                where_parts.append('m.vehicle_id = %s')
                params.append(vehicle_id)

            if status_filter == 'pending':
                where_parts.append("(m.status = 'pending' AND (m.due_date IS NULL OR m.due_date >= CURRENT_DATE))")
            elif status_filter == 'completed':
                where_parts.append("m.status = 'completed'")
            elif status_filter == 'overdue':
                where_parts.append("(m.status = 'pending' AND m.due_date IS NOT NULL AND m.due_date < CURRENT_DATE)")

            date_parts, date_params = build_date_where(okres, od, do_, alias='m')
            where_parts += date_parts
            params += date_params

            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

            base_sql = f'''
                SELECT m.*, v.name AS vname,
                       CASE
                           WHEN m.status = 'completed' THEN 'completed'
                           WHEN m.due_date IS NOT NULL AND m.due_date < CURRENT_DATE THEN 'overdue'
                           ELSE 'pending'
                       END AS effective_status
                FROM maintenance m
                JOIN vehicles v ON m.vehicle_id = v.id
                {where_sql}
                ORDER BY m.date DESC, m.created_at DESC
            '''
            count_sql = f'SELECT COUNT(*) AS count FROM maintenance m JOIN vehicles v ON m.vehicle_id = v.id {where_sql}'

            return paginate(conn, cur, count_sql, params, base_sql, params, page)
        finally:
            cur.close()

    def complete(self, entry_id: int | str) -> dict | None:
        """Mark maintenance entry as completed. Returns the entry row, or None if not found."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT id, added_by FROM maintenance WHERE id = %s', (entry_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("UPDATE maintenance SET status = 'completed' WHERE id = %s", (entry_id,))
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def create_next(self, entry_id: int | str, added_by: str | None = None) -> dict | None:
        """Clone a maintenance entry into a new pending one due 90 days later.

        The new entry is attributed to ``added_by`` when provided; otherwise the
        original entry's author is preserved.  Returns the original row, or None
        if the entry does not exist.
        """
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('''
                SELECT vehicle_id, odometer, description, notes, priority, due_date, added_by
                FROM maintenance WHERE id = %s
            ''', (entry_id,))
            row = cur.fetchone()
            if not row:
                return None

            if row['due_date']:
                normalized_due = normalize_iso_date(row['due_date'])
                if normalized_due is not None:
                    next_due = (date.fromisoformat(normalized_due) + timedelta(days=90)).isoformat()
                else:
                    next_due = (date.today() + timedelta(days=90)).isoformat()
            else:
                next_due = (date.today() + timedelta(days=90)).isoformat()

            cur.execute('''
                INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                row['vehicle_id'],
                date.today().isoformat(),
                row['odometer'],
                row['description'],
                None,
                row['notes'] or '',
                added_by if added_by is not None else row['added_by'],
                'pending',
                row['priority'] or 'medium',
                next_due,
            ))
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
