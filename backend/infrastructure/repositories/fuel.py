from backend.db import get_cursor, get_db
from backend.services.cache_service import invalidate_prefix
from backend.helpers import build_date_where, paginate, parse_positive_int
from backend.infrastructure.repositories import _to_int, _to_float
from backend.domain.exceptions import ForbiddenError, NotFoundError


class FuelRepository:
    @staticmethod
    def add(
        vehicle_id: int | str | None,
        date_val: str,
        driver: str,
        odometer: int | str | None,
        liters: float | str | None,
        cost: float | str | None,
        notes: str,
        added_by: str,
    ) -> None:
        conn = get_db()
        vehicle_id = _to_int(vehicle_id)
        odometer = _to_int(odometer)
        liters = _to_float(liters)
        cost = _to_float(cost)

        try:
            with get_cursor(conn) as cur:
                cur.execute(
                    """
                    INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        vehicle_id,
                        date_val,
                        driver,
                        odometer,
                        liters,
                        cost,
                        notes,
                        added_by,
                    ),
                )
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

    @staticmethod
    def get_by_id(entry_id: int | str) -> dict | None:
        """Return a single fuel row by primary key (with vname JOIN), or None."""
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute(
                """
                SELECT f.*, v.name AS vname
                FROM fuel f
                JOIN vehicles v ON f.vehicle_id = v.id
                WHERE f.id = %s
                LIMIT 1
                """,
                (entry_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()

    @staticmethod
    def update(
        entry_id: int | str,
        vehicle_id: int | str | None,
        date_val: str,
        driver: str,
        odometer: int | str | None,
        liters: float | str | None,
        cost: float | str | None,
        notes: str,
    ) -> None:
        """Update all mutable fields of a fuel entry. Raises NotFoundError if missing."""
        conn = get_db()
        vehicle_id = _to_int(vehicle_id)
        odometer = _to_int(odometer)
        liters = _to_float(liters)
        cost = _to_float(cost)

        try:
            with get_cursor(conn) as cur:
                cur.execute(
                    """
                    UPDATE fuel
                    SET vehicle_id = %s,
                        date       = %s,
                        driver     = %s,
                        odometer   = %s,
                        liters     = %s,
                        cost       = %s,
                        notes      = %s
                    WHERE id = %s
                    """,
                    (vehicle_id, date_val, driver, odometer, liters, cost, notes, entry_id),
                )
                if cur.rowcount == 0:
                    raise NotFoundError('Wpis tankowania nie istnieje.')
            conn.commit()
            try:
                invalidate_prefix('dashboard:')
                invalidate_prefix(f'api:last_km:{vehicle_id}')
            except Exception:
                pass
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def delete(
        entry_id: int | str,
        requester: str,
        *,
        is_admin: bool = False,
    ) -> None:
        """Delete a fuel entry.

        Raises:
            NotFoundError: when the entry does not exist.
            ForbiddenError: when the requester is neither the author nor an admin.
        """
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute(
                'SELECT id, added_by, vehicle_id FROM fuel WHERE id = %s LIMIT 1',
                (entry_id,),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError('Wpis tankowania nie istnieje.')
            if not is_admin and row.get('added_by') != requester:
                raise ForbiddenError('Brak uprawnień do usunięcia wpisu tankowania.')

            vid = row.get('vehicle_id')
            cur.execute('DELETE FROM fuel WHERE id = %s', (entry_id,))
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

    @staticmethod
    def get_page(
        *,
        vehicle_id: str | int | None = None,
        okres: str = "",
        od: str = "",
        do_: str = "",
        page: int = 1,
    ) -> tuple[list[dict], int, int, int]:
        conn = get_db()
        cur = get_cursor(conn)
        try:
            page = parse_positive_int(page, default=1)
            where_parts = []
            params = []

            if vehicle_id:
                where_parts.append("f.vehicle_id = %s")
                params.append(vehicle_id)

            date_parts, date_params = build_date_where(okres, od, do_, alias="f")
            where_parts += date_parts
            params += date_params

            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

            base_sql = f"""
                SELECT f.*, v.name AS vname FROM fuel f
                JOIN vehicles v ON f.vehicle_id = v.id
                {where_sql}
                ORDER BY f.date DESC, f.created_at DESC
            """
            count_sql = f"SELECT COUNT(*) AS count FROM fuel f JOIN vehicles v ON f.vehicle_id = v.id {where_sql}"

            return paginate(conn, cur, count_sql, params, base_sql, params, page)
        finally:
            cur.close()
