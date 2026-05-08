from datetime import date, timedelta

from backend.db import get_db, get_cursor
from backend.helpers import normalize_iso_date
from backend.services.audit_service import AuditService


def _to_int(value: str | int | None) -> int | None:
    if value in (None, ''):
        return None
    return int(value)


def _to_float(value: str | float | None) -> float | None:
    if value in (None, ''):
        return None
    return float(value)


class VehicleService:
    @staticmethod
    def get_last_km(vid: int) -> tuple[int | None, str | None]:
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
                 ORDER BY dt DESC NULLS LAST, created_at DESC NULLS LAST
                LIMIT 1
            ''', (vid, vid))
            row = cur.fetchone()
        finally:
            cur.close()

        if row and row['km'] is not None:
            return row['km'], normalize_iso_date(row['dt'])
        return None, None

    @staticmethod
    def get_recent_drivers(days: int = 90) -> list[str]:
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


class TripService:
    @staticmethod
    def add_trip(
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
    ) -> None:
        """
        equipment_used: list of dicts [{equipment_id, quantity_used, minutes_used, notes}]
        """
        conn = get_db()
        vehicle_id = _to_int(vehicle_id)
        odo_start = _to_int(odo_start)
        odo_end = _to_int(odo_end)

        try:
            with get_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by, time_start, time_end)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                    vehicle_id, date_val, driver, odo_start, odo_end, purpose, notes, added_by, time_start, time_end,
                ))
                trip_id = cur.fetchone()['id']

                if equipment_used:
                    eq_rows: list[tuple] = []
                    for eq in equipment_used:
                        eq_id = _to_int(eq.get('equipment_id'))
                        if eq_id:
                            qty = max(1, _to_int(eq.get('quantity_used')) or 1)
                            mins = _to_int(eq.get('minutes_used'))
                            eq_rows.append((trip_id, eq_id, qty, mins))
                    if eq_rows:
                        cur.executemany('''
                            MERGE INTO trip_equipment AS target
                            USING (VALUES (%s, %s, %s, %s)) AS source(trip_id, equipment_id, quantity_used, minutes_used)
                            ON target.trip_id = source.trip_id AND target.equipment_id = source.equipment_id
                            WHEN MATCHED THEN
                              UPDATE SET quantity_used = source.quantity_used, minutes_used = source.minutes_used
                            WHEN NOT MATCHED THEN
                              INSERT (trip_id, equipment_id, quantity_used, minutes_used)
                              VALUES (source.trip_id, source.equipment_id, source.quantity_used, source.minutes_used)
                        ''', eq_rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        AuditService.log('Dodanie', 'Wyjazd', f'Pojazd ID: {vehicle_id}, Kierowca: {driver}, Data: {date_val}')

    @staticmethod
    def add_fuel(
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
                cur.execute('''
                    INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    vehicle_id, date_val, driver, odometer, liters, cost, notes, added_by,
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        AuditService.log('Dodanie', 'Tankowanie', f'Pojazd ID: {vehicle_id}, Litry: {liters}, Data: {date_val}')

    @staticmethod
    def add_maintenance(
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
                ''', (
                    vehicle_id, date_val, odometer, description, cost, notes, added_by, status, priority, due_date,
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        AuditService.log('Dodanie', 'Serwis', f'Pojazd ID: {vehicle_id}, Opis: {description}, Data: {date_val}')
