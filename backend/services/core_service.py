from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import normalize_iso_date, days_since_iso_date
from backend.services.audit_service import AuditService


def _to_int(value):
    if value in (None, ''):
        return None
    return int(value)


def _to_float(value):
    if value in (None, ''):
        return None
    return float(value)


class VehicleService:
    @staticmethod
    def get_last_km(vid: int):
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
    def get_recent_drivers(days: int = 90):
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            SELECT DISTINCT driver FROM (
                SELECT driver FROM trips WHERE date >= %s
                UNION
                SELECT driver FROM fuel WHERE date >= %s
            ) ORDER BY driver ASC
        ''', (cutoff, cutoff))
        rows = cur.fetchall()
        cur.close()
        return [r['driver'] for r in rows]

class TripService:
    @staticmethod
    def add_trip(vehicle_id, date_val, driver, odo_start, odo_end, purpose, notes, added_by,
                 time_start=None, time_end=None, equipment_used=None):
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
                    vehicle_id, date_val, driver, odo_start, odo_end, purpose, notes, added_by, time_start, time_end
                ))
                trip_id = cur.fetchone()['id']

                if equipment_used:
                    eq_rows = []
                    for eq in equipment_used:
                        eq_id = _to_int(eq.get('equipment_id'))
                        if eq_id:
                            qty = max(1, _to_int(eq.get('quantity_used')) or 1)
                            mins = _to_int(eq.get('minutes_used'))
                            eq_notes = str(eq.get('notes') or '').strip()
                            eq_rows.append((trip_id, eq_id, qty, mins, eq_notes))
                    if eq_rows:
                        cur.executemany('''
                            INSERT INTO trip_equipment (trip_id, equipment_id, quantity_used, minutes_used, notes)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (trip_id, equipment_id) DO UPDATE
                            SET quantity_used = EXCLUDED.quantity_used,
                                minutes_used  = EXCLUDED.minutes_used,
                                notes         = EXCLUDED.notes
                        ''', eq_rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        AuditService.log('Dodanie', 'Wyjazd', f'Pojazd ID: {vehicle_id}, Kierowca: {driver}, Data: {date_val}')

    @staticmethod
    def add_fuel(vehicle_id, date_val, driver, odometer, liters, cost, notes, added_by):
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
                    vehicle_id, date_val, driver, odometer, liters, cost, notes, added_by
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        AuditService.log('Dodanie', 'Tankowanie', f'Pojazd ID: {vehicle_id}, Litry: {liters}, Data: {date_val}')

    @staticmethod
    def add_maintenance(vehicle_id, date_val, odometer, description, cost, notes, added_by, status, priority, due_date):
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
                    vehicle_id, date_val, odometer, description, cost, notes, added_by, status, priority, due_date
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        AuditService.log('Dodanie', 'Serwis', f'Pojazd ID: {vehicle_id}, Opis: {description}, Data: {date_val}')
