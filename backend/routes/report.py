from flask import Blueprint, render_template, request, flash, current_app
from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import login_required

report_bp = Blueprint('report', __name__)

@report_bp.route('/raport', endpoint='report')
@login_required
def report():
    today = date.today()
    month_str = request.args.get('month', today.strftime('%Y-%m'))
    vid = request.args.get('vehicle_id', '')

    try:
        year, month = int(month_str[:4]), int(month_str[5:7])
        if month < 1 or month > 12:
            raise ValueError('Invalid month range')
    except (ValueError, IndexError):
        year, month = today.year, today.month
        month_str = today.strftime('%Y-%m')

    first_day = date(year, month, 1).isoformat()
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    last_day = last_day.isoformat()
    conn = get_db()
    cur = get_cursor(conn)

    try:
        cur.execute('SELECT * FROM vehicles ORDER BY active DESC, name')
        vehicles = cur.fetchall()

        trip_where = "WHERE t.date BETWEEN %s AND %s"
        trip_params = [first_day, last_day]
        if vid:
            trip_where += " AND t.vehicle_id = %s"
            trip_params.append(vid)

        cur.execute(f'''
            SELECT t.*, v.name AS vname
            FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
            {trip_where}
            ORDER BY t.date, t.created_at
        ''', trip_params)
        trip_entries = cur.fetchall()

        cur.execute(f'''
            SELECT v.id, v.name, v.plate,
                   COUNT(t.id) AS trip_count,
                   SUM(CASE WHEN t.odo_end IS NOT NULL AND t.odo_start IS NOT NULL
                            THEN t.odo_end - t.odo_start ELSE 0 END) AS total_km
            FROM vehicles v
            LEFT JOIN trips t ON t.vehicle_id = v.id AND t.date BETWEEN %s AND %s
            {"AND t.vehicle_id = %s" if vid else ""}
            GROUP BY v.id, v.name, v.plate
            HAVING COUNT(t.id) > 0
            ORDER BY v.name
        ''', [first_day, last_day] + ([vid] if vid else []))
        trip_summary = cur.fetchall()

        fuel_where = "WHERE f.date BETWEEN %s AND %s"
        fuel_params = [first_day, last_day]
        if vid:
            fuel_where += " AND f.vehicle_id = %s"
            fuel_params.append(vid)

        cur.execute(f'''
            SELECT vehicle_id, SUM(liters) AS total_liters, SUM(cost) AS total_cost
            FROM fuel f
            {fuel_where}
            GROUP BY vehicle_id
        ''', fuel_params)
        fuel_summary = cur.fetchall()
        fuel_by_vid = {r['vehicle_id']: r for r in fuel_summary}

        maint_where = "WHERE m.date BETWEEN %s AND %s"
        maint_params = [first_day, last_day]
        if vid:
            maint_where += " AND m.vehicle_id = %s"
            maint_params.append(vid)

        cur.execute(f'''
            SELECT vehicle_id, SUM(cost) AS total_cost
            FROM maintenance m
            {maint_where}
            GROUP BY vehicle_id
        ''', maint_params)
        maint_summary = cur.fetchall()
        maint_by_vid = {r['vehicle_id']: r for r in maint_summary}

        return render_template('report.html',
                               vehicles=vehicles,
                               trip_summary=trip_summary,
                               fuel_by_vid=fuel_by_vid,
                               maint_by_vid=maint_by_vid,
                               trip_entries=trip_entries,
                               month_str=month_str,
                               selected_vehicle=vid,
                               first_day=first_day,
                               last_day=last_day)
    except Exception:
        current_app.logger.exception('Błąd generowania raportu miesięcznego')
        flash('Nie udało się wygenerować raportu. Sprawdź dane i spróbuj ponownie.', 'error')
        return render_template('report.html',
                               vehicles=[],
                               trip_summary=[],
                               fuel_by_vid={},
                               maint_by_vid={},
                               trip_entries=[],
                               month_str=month_str,
                               selected_vehicle=vid,
                               first_day=first_day,
                               last_day=last_day)
    finally:
        cur.close()