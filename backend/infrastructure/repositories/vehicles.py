from __future__ import annotations

from datetime import date, timedelta
from threading import Lock

from backend.db import get_db, get_cursor
from backend.domain.exceptions import ForbiddenError, NotFoundError
from backend.helpers import normalize_iso_date
from backend.infrastructure.repositories import _to_int

_vehicles_has_active_column: bool | None = None
_vehicle_schema_lock = Lock()


class VehicleRepository:
    def get_all(self) -> list[dict]:
        """All vehicles ordered by name."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT * FROM vehicles ORDER BY name')
            return cur.fetchall()
        finally:
            cur.close()

    def get_active(self, vehicle_id: str | int | None) -> dict | None:
        """Return vehicle row if it exists and is active, else None."""
        global _vehicles_has_active_column
        try:
            vid = int(vehicle_id)
        except (TypeError, ValueError):
            return None
        if vid <= 0:
            return None

        conn = get_db()
        cur = get_cursor(conn)
        try:
            if _vehicles_has_active_column is None:
                with _vehicle_schema_lock:
                    if _vehicles_has_active_column is None:
                        cur.execute("""
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_name = 'vehicles' AND column_name = 'active'
                            LIMIT 1
                        """)
                        _vehicles_has_active_column = cur.fetchone() is not None

            if _vehicles_has_active_column:
                cur.execute('''
                    SELECT *
                    FROM vehicles
                    WHERE id = %s
                      AND COALESCE(active::text, '1') IN ('1', 'true', 't')
                    LIMIT 1
                ''', (vid,))
            else:
                cur.execute('SELECT * FROM vehicles WHERE id = %s LIMIT 1', (vid,))
            return cur.fetchone()
        finally:
            cur.close()

    def get_by_id(self, vid: int) -> dict | None:
        """Return vehicle row by PK regardless of active status, or None."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT * FROM vehicles WHERE id = %s LIMIT 1', (vid,))
            return cur.fetchone()
        finally:
            cur.close()

    def get_last_km(self, vid: int) -> tuple[int | None, str | None]:
        """Return (km, date_str) for the most recent odometer reading."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('''
                SELECT km, dt FROM (
                     SELECT odo_end AS km, date AS dt, created_at
                     FROM trips
                     WHERE vehicle_id = %s AND odo_end IS NOT NULL
                     ORDER BY date DESC NULLS LAST, created_at DESC NULLS LAST
                     LIMIT 1
                 ) latest_trip
                 UNION ALL
                 SELECT km, dt FROM (
                     SELECT odometer AS km, date AS dt, created_at
                     FROM fuel
                     WHERE vehicle_id = %s AND odometer IS NOT NULL
                     ORDER BY date DESC NULLS LAST, created_at DESC NULLS LAST
                     LIMIT 1
                 ) latest_fuel
                 ORDER BY dt DESC NULLS LAST
                LIMIT 1
            ''', (vid, vid))
            row = cur.fetchone()
        finally:
            cur.close()

        if row and row['km'] is not None:
            return row['km'], normalize_iso_date(row['dt'])
        return None, None

    def get_recent_drivers(self, days: int = 90) -> list[str]:
        """Return distinct driver names from the last *days* days."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('''
                SELECT DISTINCT driver FROM (
                    SELECT driver FROM trips WHERE date >= %s
                    UNION
                    SELECT driver FROM fuel WHERE date >= %s
                ) ORDER BY driver ASC
            ''', (cutoff, cutoff))
            rows = cur.fetchall()
        finally:
            cur.close()
        return [r['driver'] for r in rows]

    def add(self, name: str, plate: str, type_: str) -> None:
        """Insert a new vehicle."""
        conn = get_db()
        try:
            with get_cursor(conn) as cur:
                cur.execute(
                    'INSERT INTO vehicles (name, plate, type) VALUES (%s, %s, %s)',
                    (name, plate, type_),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def update(self, vid: int, name: str, plate: str, type_: str) -> None:
        """Update an existing vehicle."""
        conn = get_db()
        try:
            with get_cursor(conn) as cur:
                cur.execute(
                    'UPDATE vehicles SET name=%s, plate=%s, type=%s WHERE id=%s',
                    (name, plate, type_, vid),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def delete(self, vid: int) -> None:
        """Delete a vehicle. Raises NotFoundError/ForbiddenError."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT id FROM vehicles WHERE id = %s', (vid,))
            if not cur.fetchone():
                raise NotFoundError('Pojazd nie istnieje.')

            if self.has_linked_rows(vid):
                raise ForbiddenError(
                    'Nie można usunąć pojazdu — posiada przypisane wpisy '
                    '(wyjazdy/tankowania/serwis). Najpierw usuń powiązane wpisy.'
                )

            cur.execute('DELETE FROM vehicles WHERE id = %s', (vid,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def has_linked_rows(self, vid: int) -> bool:
        """Returns True if vehicle has trips, fuel, or maintenance rows."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute(
                'SELECT (SELECT COUNT(*) FROM trips WHERE vehicle_id = %s) + '
                '       (SELECT COUNT(*) FROM fuel WHERE vehicle_id = %s) + '
                '       (SELECT COUNT(*) FROM maintenance WHERE vehicle_id = %s) AS count',
                (vid, vid, vid),
            )
            return cur.fetchone()['count'] > 0
        finally:
            cur.close()
