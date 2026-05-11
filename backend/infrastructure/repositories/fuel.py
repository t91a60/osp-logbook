from backend.db import get_cursor, get_db
from backend.services.cache_service import invalidate_prefix
from backend.helpers import build_date_where, paginate, parse_positive_int
from backend.infrastructure.repositories import _to_int, _to_float


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
