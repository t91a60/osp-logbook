from flask import render_template, request, abort
from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import login_required


def _quarter_date_range(year, quarter):
    if quarter == 1:
        return date(year, 1, 1), date(year, 3, 31)
    if quarter == 2:
        return date(year, 4, 1), date(year, 6, 30)
    if quarter == 3:
        return date(year, 7, 1), date(year, 9, 30)
    return date(year, 10, 1), date(year, 12, 31)


def _parse_period(period, today):
    # YYYY-MM
    if len(period) == 7 and period[4] == '-':
        try:
            year = int(period[:4])
            month = int(period[5:7])
            first = date(year, month, 1)
            if month == 12:
                last = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                last = date(year, month + 1, 1) - timedelta(days=1)
            return first, last, first.strftime('%m/%Y')
        except ValueError:
            pass

    # YYYY-QN
    if len(period) == 7 and period[4] == '-' and period[5].upper() == 'Q':
        try:
            year = int(period[:4])
            quarter = int(period[6])
            if quarter not in (1, 2, 3, 4):
                raise ValueError
            first, last = _quarter_date_range(year, quarter)
            return first, last, f'Q{quarter} {year}'
        except ValueError:
            pass

    # Fallback to current month
    first = date(today.year, today.month, 1)
    if today.month == 12:
        last = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(today.year, today.month + 1, 1) - timedelta(days=1)
    return first, last, first.strftime('%m/%Y')


def register_routes(app):
    @app.route('/raport', endpoint='report')
    @login_required
    def report():
        conn = get_db()
        cur = get_cursor(conn)
        today = date.today()
        month_str = request.args.get('month', today.strftime('%Y-%m'))
        vid = request.args.get('vehicle_id', '')

        try:
            year, month = int(month_str[:4]), int(month_str[5:7])
        except (ValueError, IndexError):
            year, month = today.year, today.month
            month_str = today.strftime('%Y-%m')

        first_day = date(year, month, 1).isoformat()
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        last_day = last_day.isoformat()

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

        summary_where = "WHERE t.date BETWEEN %s AND %s"
        summary_params = [first_day, last_day]
        if vid:
            summary_where += " AND t.vehicle_id = %s"
            summary_params.append(vid)

        cur.execute(f'''
            SELECT v.id, v.name, v.plate,
                   COUNT(t.id) AS trip_count,
                   SUM(CASE WHEN t.odo_end IS NOT NULL AND t.odo_start IS NOT NULL
                            THEN t.odo_end - t.odo_start ELSE 0 END) AS total_km
            FROM vehicles v
            LEFT JOIN trips t ON t.vehicle_id = v.id AND t.date BETWEEN %s AND %s
            {"AND t.vehicle_id = %s" if vid else ""}
            GROUP BY v.id
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

        cur.close()

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

    @app.route('/report/print/<int:vehicle_id>/<string:period>', endpoint='report_print_vehicle')
    @login_required
    def report_print_vehicle(vehicle_id, period):
        conn = get_db()
        cur = get_cursor(conn)
        today = date.today()

        first_dt, last_dt, period_label = _parse_period(period, today)
        first_day = first_dt.isoformat()
        last_day = last_dt.isoformat()

        try:
            cur.execute('SELECT id, name, plate, type, active FROM vehicles WHERE id = %s', (vehicle_id,))
            vehicle = cur.fetchone()
            if not vehicle:
                abort(404)

            cur.execute('''
                SELECT id, date, driver, purpose, notes, odo_start, odo_end
                FROM trips
                WHERE vehicle_id = %s AND date BETWEEN %s AND %s
                ORDER BY date ASC, created_at ASC
            ''', (vehicle_id, first_day, last_day))
            entries = cur.fetchall()
        finally:
            cur.close()

        rows = []
        folio_sum = 0
        for idx, trip in enumerate(entries, start=1):
            odo_start = trip['odo_start'] if trip['odo_start'] is not None else ''
            odo_end = trip['odo_end'] if trip['odo_end'] is not None else ''
            trip_km = ''
            if trip['odo_start'] is not None and trip['odo_end'] is not None:
                trip_km = max(0, trip['odo_end'] - trip['odo_start'])
                folio_sum += trip_km

            rows.append({
                'no': idx,
                'date': trip['date'],
                'driver': trip['driver'],
                'purpose': trip['purpose'],
                'odo_start': odo_start,
                'odo_end': odo_end,
                'trip_km': trip_km,
                'route_desc': '',
                'remarks': trip['notes'] or ''
            })

        carry_over = 0
        period_total = carry_over + folio_sum

        return render_template('templates/print_vehicle_log.html',
                               vehicle=vehicle,
                               period=period,
                               period_label=period_label,
                               first_day=first_day,
                               last_day=last_day,
                               generated_on=today.isoformat(),
                               rows=rows,
                               folio_sum=folio_sum,
                               carry_over=carry_over,
                               period_total=period_total)