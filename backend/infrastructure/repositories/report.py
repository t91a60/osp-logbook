from typing import Any, Optional

from backend.db import get_cursor, get_db
from backend.services.cache_service import cached


class ReportRepository:
    """Repository odpowiedzialny za zapytania do raportów okresowych."""

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_trip_entries(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> list[dict[str, Any]]:
        def _execute(cursor) -> list[dict[str, Any]]:
            trip_where = "WHERE t.date BETWEEN %s AND %s"
            trip_params = [first_day, last_day]
            if vid:
                trip_where += " AND t.vehicle_id = %s"
                trip_params.append(str(vid))

            cursor.execute(f"""
                SELECT
                    t.id, t.date, t.driver, t.purpose,
                    t.odo_start, t.odo_end,
                    t.time_start, t.time_end,
                    t.notes, t.created_at,
                    v.name AS vname
                FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
                {trip_where}
                ORDER BY t.date, t.created_at
            """, trip_params)
            return list(cursor.fetchall())

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_total_km(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> int:
        def _execute(cursor) -> int:
            total_km_where = "WHERE date BETWEEN %s AND %s"
            total_km_params = [first_day, last_day]
            if vid:
                total_km_where += " AND vehicle_id = %s"
                total_km_params.append(vid)

            cursor.execute(f"""
                SELECT COALESCE(SUM(
                    CASE
                        WHEN odo_end IS NOT NULL AND odo_start IS NOT NULL
                            THEN odo_end - odo_start
                        ELSE 0
                    END
                ), 0) AS total_km
                FROM trips
                {total_km_where}
            """, total_km_params)
            return cursor.fetchone()['total_km']

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_trip_summary(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> list[dict[str, Any]]:
        def _execute(cursor) -> list[dict[str, Any]]:
            cursor.execute(f"""
                SELECT v.id, v.name, v.plate,
                       COUNT(t.id) AS trip_count,
                       SUM(CASE WHEN t.odo_end IS NOT NULL AND t.odo_start IS NOT NULL
                                THEN t.odo_end - t.odo_start ELSE 0 END) AS total_km
                FROM vehicles v
                LEFT JOIN trips t
                    ON t.vehicle_id = v.id
                    AND t.date BETWEEN %s AND %s
                    {"AND t.vehicle_id = %s" if vid else ""}
                GROUP BY v.id
                HAVING COUNT(t.id) > 0
                ORDER BY v.name
            """, [first_day, last_day] + ([vid] if vid else []))
            return list(cursor.fetchall())

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_fuel_summary(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> dict[int, dict[str, Any]]:
        def _execute(cursor) -> dict[int, dict[str, Any]]:
            fuel_where = "WHERE f.date BETWEEN %s AND %s"
            fuel_params = [first_day, last_day]
            if vid:
                fuel_where += " AND f.vehicle_id = %s"
                fuel_params.append(str(vid))

            cursor.execute(f"""
                SELECT vehicle_id,
                       SUM(liters) AS total_liters,
                       SUM(cost)   AS total_cost
                FROM fuel f
                {fuel_where}
                GROUP BY vehicle_id
            """, fuel_params)
            return {r['vehicle_id']: dict(r) for r in cursor.fetchall()}

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_maintenance_summary(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> dict[int, dict[str, Any]]:
        def _execute(cursor) -> dict[int, dict[str, Any]]:
            maint_where = "WHERE m.date BETWEEN %s AND %s"
            maint_params = [first_day, last_day]
            if vid:
                maint_where += " AND m.vehicle_id = %s"
                maint_params.append(str(vid))

            cursor.execute(f"""
                SELECT vehicle_id, SUM(cost) AS total_cost
                FROM maintenance m
                {maint_where}
                GROUP BY vehicle_id
            """, maint_params)
            return {r['vehicle_id']: dict(r) for r in cursor.fetchall()}

        return self._run_with_cursor(cur, _execute)

    def _run_with_cursor(self, provided_cur: Optional[Any], func: callable) -> Any:
        if provided_cur is not None:
            return func(provided_cur)
        
        conn = get_db()
        cur = get_cursor(conn)
        try:
            return func(cur)
        finally:
            cur.close()
