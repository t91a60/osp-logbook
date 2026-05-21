from typing import Any, Optional

from backend.db import get_cursor, get_db
from backend.services.cache_service import cached


class ReportRepository:
    """Repository odpowiedzialny za zapytania do raportów okresowych."""

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_trip_entries(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> list[dict[str, Any]]:
        def _execute(cursor) -> list[dict[str, Any]]:
            trip_where_parts = ["t.deleted_at IS NULL", "t.date BETWEEN %s AND %s"]
            trip_params = [first_day, last_day]
            if vid:
                trip_where_parts.append("t.vehicle_id = %s")
                trip_params.append(str(vid))
            trip_where = "WHERE " + " AND ".join(trip_where_parts)

            cursor.execute(
                """
                SELECT
                    t.id, t.date, t.driver, t.purpose,
                    t.odo_start, t.odo_end,
                    t.time_start, t.time_end,
                    t.notes, t.created_at,
                    v.name AS vname
                FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
                """
                + trip_where
                + """
                ORDER BY t.date, t.created_at
                """,
                trip_params,
            )
            return list(cursor.fetchall())

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_total_km(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> int:
        def _execute(cursor) -> int:
            total_km_where_parts = ["deleted_at IS NULL", "date BETWEEN %s AND %s"]
            total_km_params = [first_day, last_day]
            if vid:
                total_km_where_parts.append("vehicle_id = %s")
                total_km_params.append(vid)
            total_km_where = "WHERE " + " AND ".join(total_km_where_parts)

            cursor.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN odo_end IS NOT NULL AND odo_start IS NOT NULL
                            THEN odo_end - odo_start
                        ELSE 0
                    END
                ), 0) AS total_km
                FROM trips
                """
                + total_km_where,
                total_km_params,
            )
            return cursor.fetchone()['total_km']

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_trip_summary(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> list[dict[str, Any]]:
        def _execute(cursor) -> list[dict[str, Any]]:
            join_conditions = [
                "t.vehicle_id = v.id",
                "t.deleted_at IS NULL",
                "t.date BETWEEN %s AND %s",
            ]
            trip_params = [first_day, last_day]
            if vid:
                join_conditions.append("t.vehicle_id = %s")
                trip_params.append(vid)

            cursor.execute(
                """
                SELECT v.id, v.name, v.plate,
                       COUNT(t.id) AS trip_count,
                       SUM(CASE WHEN t.odo_end IS NOT NULL AND t.odo_start IS NOT NULL
                                 THEN t.odo_end - t.odo_start ELSE 0 END) AS total_km
                FROM vehicles v
                LEFT JOIN trips t ON
                """
                + " AND ".join(join_conditions)
                + """
                GROUP BY v.id
                HAVING COUNT(t.id) > 0
                ORDER BY v.name
                """,
                trip_params,
            )
            return list(cursor.fetchall())

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_fuel_summary(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> dict[int, dict[str, Any]]:
        def _execute(cursor) -> dict[int, dict[str, Any]]:
            fuel_where_parts = ["f.deleted_at IS NULL", "f.date BETWEEN %s AND %s"]
            fuel_params = [first_day, last_day]
            if vid:
                fuel_where_parts.append("f.vehicle_id = %s")
                fuel_params.append(str(vid))
            fuel_where = "WHERE " + " AND ".join(fuel_where_parts)

            cursor.execute(
                """
                SELECT vehicle_id,
                       SUM(liters) AS total_liters,
                       SUM(cost)   AS total_cost
                FROM fuel f
                """
                + fuel_where
                + """
                GROUP BY vehicle_id
                """,
                fuel_params,
            )
            return {r['vehicle_id']: dict(r) for r in cursor.fetchall()}

        return self._run_with_cursor(cur, _execute)

    @cached(ttl=300, tags=['report', 'report:{vid}'])
    def get_maintenance_summary(self, first_day: str, last_day: str, vid: int = 0, cur: Optional[Any] = None) -> dict[int, dict[str, Any]]:
        def _execute(cursor) -> dict[int, dict[str, Any]]:
            maint_where_parts = ["m.deleted_at IS NULL", "m.date BETWEEN %s AND %s"]
            maint_params = [first_day, last_day]
            if vid:
                maint_where_parts.append("m.vehicle_id = %s")
                maint_params.append(str(vid))
            maint_where = "WHERE " + " AND ".join(maint_where_parts)

            cursor.execute(
                """
                SELECT vehicle_id, SUM(cost) AS total_cost
                FROM maintenance m
                """
                + maint_where
                + """
                GROUP BY vehicle_id
                """,
                maint_params,
            )
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
