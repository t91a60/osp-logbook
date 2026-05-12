from typing import Any, Optional

from backend.db import get_cursor, get_db


class DashboardRepository:
    """Repository odpowiedzialny za wszystkie zapytania SQL widoku dashboardu."""

    def get_vehicle_cards(self, cur: Optional[Any] = None) -> list[dict[str, Any]]:
        """Zwraca dane do kart pojazdów (ostatni przebieg + data)."""

        def _execute(cursor) -> list[dict[str, Any]]:
            cursor.execute("""
                WITH trip_max AS (
                    SELECT vehicle_id, MAX(odo_end) AS last_km, MAX(date) AS last_km_date
                    FROM trips WHERE odo_end IS NOT NULL GROUP BY vehicle_id
                ),
                fuel_max AS (
                    SELECT vehicle_id, MAX(odometer) AS last_km, MAX(date) AS last_km_date
                    FROM fuel WHERE odometer IS NOT NULL GROUP BY vehicle_id
                ),
                last_trip_date AS (
                    SELECT vehicle_id, MAX(date) AS last_trip_date
                    FROM trips GROUP BY vehicle_id
                )
                SELECT
                    v.id, v.name, v.plate, v.type,
                    CASE
                        WHEN tm.last_km IS NULL THEN fm.last_km
                        WHEN fm.last_km IS NULL THEN tm.last_km
                        WHEN (tm.last_km_date >= fm.last_km_date) THEN tm.last_km
                        ELSE fm.last_km
                    END AS last_km,
                    ltd.last_trip_date
                FROM vehicles v
                LEFT JOIN trip_max       tm ON tm.vehicle_id = v.id
                LEFT JOIN fuel_max       fm ON fm.vehicle_id = v.id
                LEFT JOIN last_trip_date ltd ON ltd.vehicle_id = v.id
                ORDER BY v.name
            """)
            return cursor.fetchall()

        return self._run_with_cursor(cur, _execute)

    def get_recent_trips(
        self, limit: int = 6, cur: Optional[Any] = None
    ) -> list[dict[str, Any]]:
        def _execute(cursor):
            cursor.execute(
                """
                SELECT t.*, v.name AS vname
                FROM trips t
                JOIN vehicles v ON t.vehicle_id = v.id
                ORDER BY t.date DESC, t.created_at DESC
                LIMIT %s
            """,
                (limit,),
            )
            return cursor.fetchall()

        return self._run_with_cursor(cur, _execute)

    def get_recent_fuel(
        self, limit: int = 4, cur: Optional[Any] = None
    ) -> list[dict[str, Any]]:
        def _execute(cursor):
            cursor.execute(
                """
                SELECT f.*, v.name AS vname
                FROM fuel f
                JOIN vehicles v ON f.vehicle_id = v.id
                ORDER BY f.date DESC, f.created_at DESC
                LIMIT %s
            """,
                (limit,),
            )
            return cursor.fetchall()

        return self._run_with_cursor(cur, _execute)

    def get_aggregate_stats(self, cur: Optional[Any] = None) -> dict[str, int]:
        def _execute(cursor):
            cursor.execute("""
                SELECT
                    (SELECT COUNT(*) FROM trips)       AS trips_count,
                    (SELECT COUNT(*) FROM fuel)        AS fuel_count,
                    (SELECT COUNT(*) FROM maintenance) AS maint_count
            """)
            row = cursor.fetchone()
            return {
                "trips": row["trips_count"] or 0,
                "fuel": row["fuel_count"] or 0,
                "maintenance": row["maint_count"] or 0,
            }

        return self._run_with_cursor(cur, _execute)

    def _run_with_cursor(self, provided_cur: Optional[Any], func: callable) -> Any:
        """Uruchamia operację z podanym kursorem lub tworzy własny."""
        if provided_cur is not None:
            return func(provided_cur)

        conn = get_db()
        cur = get_cursor(conn)
        try:
            return func(cur)
        finally:
            cur.close()
