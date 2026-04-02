from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import normalize_iso_date, days_since_iso_date

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
        cur = get_cursor(conn)
        cur.execute('''
            INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            vehicle_id, date_val, driver, odo_start, odo_end, purpose, notes, added_by
        ))
        conn.commit()
        cur.close()

    @staticmethod
    def add_fuel(vehicle_id, date_val, driver, odometer, liters, cost, notes, added_by):
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            vehicle_id, date_val, driver, odometer, liters, cost, notes, added_by
        ))
        conn.commit()
        cur.close()

    @staticmethod
    def add_maintenance(vehicle_id, date_val, odometer, description, cost, notes, added_by, status, priority, due_date):
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            vehicle_id, date_val, odometer, description, cost, notes, added_by, status, priority, due_date
        ))
        conn.commit()
        cur.close()
