from __future__ import annotations

from backend.db import get_cursor, get_db
from backend.services.cache_service import invalidate_prefix
from backend.domain.exceptions import ForbiddenError, NotFoundError
from backend.helpers import (
    build_date_where,
    paginate,
    parse_positive_int,
)
from backend.infrastructure.repositories import _to_int


class TripRepository:
    def add(
        self,
        vehicle_id: int | str | None,
        date_val: str,
        driver: str,
        odo_start: int | str | None,
        odo_end: int | str | None,
        purpose: str,
        notes: str,
        added_by: str,
        *,
        time_start: str | None = None,
        time_end: str | None = None,
        equipment_used: list[dict] | None = None,
    ) -> int:
        conn = get_db()
        vehicle_id = _to_int(vehicle_id)
        odo_start = _to_int(odo_start)
        odo_end = _to_int(odo_end)

        try:
            with get_cursor(conn) as cur:
                cur.execute(
                    """
                    INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by, time_start, time_end)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        vehicle_id,
                        date_val,
                        driver,
                        odo_start,
                        odo_end,
                        purpose,
                        notes,
                        added_by,
                        time_start,
                        time_end,
                    ),
                )
                trip_id = cur.fetchone()["id"]

                if equipment_used:
                    eq_rows: list[tuple] = []
                    for eq in equipment_used:
                        eq_id = _to_int(eq.get("equipment_id"))
                        if eq_id:
                            qty = max(1, _to_int(eq.get("quantity_used")) or 1)
                            mins = _to_int(eq.get("minutes_used"))
                            eq_rows.append((trip_id, eq_id, qty, mins))
                    if eq_rows:
                        cur.executemany(
                            """
                            MERGE INTO trip_equipment AS target
                            USING (VALUES (%s, %s, %s, %s)) AS source(trip_id, equipment_id, quantity_used, minutes_used)
                            ON target.trip_id = source.trip_id AND target.equipment_id = source.equipment_id
                            WHEN MATCHED THEN
                              UPDATE SET quantity_used = source.quantity_used, minutes_used = source.minutes_used
                            WHEN NOT MATCHED THEN
                              INSERT (trip_id, equipment_id, quantity_used, minutes_used)
                              VALUES (source.trip_id, source.equipment_id, source.quantity_used, source.minutes_used)
                        """,
                            eq_rows,
                        )
            conn.commit()
            # Invalidate dashboard snapshot and last-km cache so UIs refresh immediately
            try:
                invalidate_prefix('dashboard:')
                invalidate_prefix(f'api:last_km:{vehicle_id}')
            except Exception:
                # Don't fail the DB write if cache invalidation has issues
                pass
            return trip_id
        except Exception:
            conn.rollback()
            raise

    def get_page(
        self,
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
                where_parts.append("t.vehicle_id = %s")
                params.append(vehicle_id)

            date_parts, date_params = build_date_where(okres, od, do_, alias="t")
            where_parts += date_parts
            params += date_params

            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

            base_sql = f"""
                SELECT t.*, v.name AS vname FROM trips t
                JOIN vehicles v ON t.vehicle_id = v.id
                {where_sql}
                ORDER BY t.date DESC, t.created_at DESC
            """
            count_sql = f"SELECT COUNT(*) AS count FROM trips t JOIN vehicles v ON t.vehicle_id = v.id {where_sql}"

            return paginate(conn, cur, count_sql, params, base_sql, params, page)
        finally:
            cur.close()

    def get_by_id(self, trip_id: int | str) -> dict | None:
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute(
                """
                SELECT t.*, v.name AS vname
                FROM trips t
                JOIN vehicles v ON t.vehicle_id = v.id
                WHERE t.id = %s
                LIMIT 1
            """,
                (trip_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()

    def delete(
        self,
        trip_id: int | str,
        requester: str,
        *,
        is_admin: bool = False,
    ) -> None:
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute(
                "SELECT id, added_by FROM trips WHERE id = %s LIMIT 1", (trip_id,)
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError("Wyjazd nie istnieje.")
            if not is_admin and row.get("added_by") != requester:
                raise ForbiddenError("Brak uprawnień do usunięcia wyjazdu.")

            cur.execute("DELETE FROM trip_equipment WHERE trip_id = %s", (trip_id,))
            cur.execute("DELETE FROM trips WHERE id = %s", (trip_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
