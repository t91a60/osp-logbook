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
        
        cur.execute(
            "SELECT MAX(odo_end) as km, MAX(date) as dt FROM trips WHERE vehicle_id = %s AND odo_end IS NOT NULL",
            (vid,)
        )
        trip_row = cur.fetchone()
        
        cur.execute(
            "SELECT MAX(odometer) as km, MAX(date) as dt FROM fuel WHERE vehicle_id = %s AND odometer IS NOT NULL",
            (vid,)
        )
        fuel_row = cur.fetchone()
        cur.close()

        trip_km = trip_row['km'] if trip_row and trip_row['km'] else None
        fuel_km = fuel_row['km'] if fuel_row and fuel_row['km'] else None
        trip_dt = normalize_iso_date(trip_row['dt']) if trip_row and trip_row['dt'] else None
        fuel_dt = normalize_iso_date(fuel_row['dt']) if fuel_row and fuel_row['dt'] else None

        km = None
        dt = None
        
        if trip_km is not None and fuel_km is not None:
            if (trip_dt or '') >= (fuel_dt or ''):
                km, dt = trip_km, trip_dt
            else:
                km, dt = fuel_km, fuel_dt
        elif trip_km is not None:
            km, dt = trip_km, trip_dt
        elif fuel_km is not None:
            km, dt = fuel_km, fuel_dt

        return km, dt

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
    def add_trip(vehicle_id, date_val, driver, odo_start, odo_end, purpose, notes, added_by):
        conn = get_db()
        vehicle_id = _to_int(vehicle_id)
        odo_start = _to_int(odo_start)
        odo_end = _to_int(odo_end)

        try:
            with get_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    vehicle_id, date_val, driver, odo_start, odo_end, purpose, notes, added_by
                ))
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
