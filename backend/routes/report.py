from datetime import date, timedelta

from flask import abort, render_template, request

from backend.db import get_cursor, get_db
from backend.helpers import login_required, parse_positive_int
from backend.services.cache_service import get_vehicles_cached

_POLISH_MONTHS = [
    'styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec',
    'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień',
]


def _parse_period(period):
    today = date.today()

    if '-Q' in period:
        try:
            year_text, quarter_text = period.split('-Q', 1)
            year = int(year_text)
            quarter = int(quarter_text)
            if quarter not in (1, 2, 3, 4):
                raise ValueError
        except ValueError:
            year = today.year
            quarter = (today.month - 1) // 3 + 1
        start_month = (quarter - 1) * 3 + 1
        first_day = date(year, start_month, 1)
        if quarter == 4:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, start_month + 3, 1) - timedelta(days=1)
        return first_day, last_day, f'Q{quarter} {year}'

    try:
        year, month = int(period[:4]), int(period[5:7])
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        return first_day, last_day, period
    except (ValueError, IndexError):
        first_day = today.replace(day=1)
        if today.month == 12:
            last_day = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return first_day, last_day, today.strftime('%Y-%m')


def register_routes(app):
    @app.route('/raport', endpoint='report')
    @login_required
    def report():
        conn = get_db()
        cur = get_cursor(conn)
        try:
            today = date.today()
            month_str = request.args.get('month', today.strftime('%Y-%m'))
            vid = parse_positive_int(request.args.get('vehicle_id'), default=0)
            selected_vehicle = str(vid) if vid else ''

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

            vehicles = get_vehicles_cached()
            report_vehicle = next((v for v in vehicles if str(v['id']) == selected_vehicle), None)
            period_label = f'{_POLISH_MONTHS[month - 1]} {year}'

            trip_where_parts = ["t.deleted_at IS NULL", "t.date BETWEEN %s AND %s"]
            trip_params = [first_day, last_day]
            if vid:
                trip_where_parts.append("t.vehicle_id = %s")
                trip_params.append(str(vid))
            trip_where = "WHERE " + " AND ".join(trip_where_parts)

            cur.execute(
                '''
                SELECT
                    t.id,
                    t.date,
                    t.driver,
                    t.purpose,
                    t.odo_start,
                    t.odo_end,
                    t.time_start,
                    t.time_end,
                    t.notes,
                    t.created_at,
                    v.name AS vname
                FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
                '''
                + trip_where
                + '''
                ORDER BY t.date, t.created_at
                ''',
                trip_params,
            )
            trip_entries = cur.fetchall()

            total_km_where_parts = ["deleted_at IS NULL", "date BETWEEN %s AND %s"]
            total_km_params = [first_day, last_day]
            if vid:
                total_km_where_parts.append("vehicle_id = %s")
                total_km_params.append(vid)
            total_km_where = "WHERE " + " AND ".join(total_km_where_parts)

            cur.execute(
                '''
                SELECT COALESCE(SUM(
                    CASE
                        WHEN odo_end IS NOT NULL AND odo_start IS NOT NULL THEN odo_end - odo_start
                        ELSE 0
                    END
                ), 0) AS total_km
                FROM trips
                '''
                + total_km_where,
                total_km_params,
            )
            total_km = cur.fetchone()['total_km']

            trip_join_conditions = [
                't.vehicle_id = v.id',
                't.deleted_at IS NULL',
                't.date BETWEEN %s AND %s',
            ]
            trip_summary_params = [first_day, last_day]
            if vid:
                trip_join_conditions.append('t.vehicle_id = %s')
                trip_summary_params.append(vid)

            cur.execute(
                '''
                SELECT v.id, v.name, v.plate,
                       COUNT(t.id) AS trip_count,
                       SUM(
                           CASE
                               WHEN t.odo_end IS NOT NULL AND t.odo_start IS NOT NULL
                                   THEN t.odo_end - t.odo_start
                               ELSE 0
                           END
                       ) AS total_km
                FROM vehicles v
                LEFT JOIN trips t ON
                '''
                + ' AND '.join(trip_join_conditions)
                + '''
                GROUP BY v.id
                HAVING COUNT(t.id) > 0
                ORDER BY v.name
                ''',
                trip_summary_params,
            )
            trip_summary = cur.fetchall()

            fuel_where_parts = ["f.deleted_at IS NULL", "f.date BETWEEN %s AND %s"]
            fuel_params = [first_day, last_day]
            if vid:
                fuel_where_parts.append("f.vehicle_id = %s")
                fuel_params.append(str(vid))
            fuel_where = "WHERE " + " AND ".join(fuel_where_parts)

            cur.execute(
                '''
                SELECT vehicle_id, SUM(liters) AS total_liters, SUM(cost) AS total_cost
                FROM fuel f
                '''
                + fuel_where
                + '''
                GROUP BY vehicle_id
                ''',
                fuel_params,
            )
            fuel_summary = cur.fetchall()
            fuel_by_vid = {r['vehicle_id']: r for r in fuel_summary}

            maint_where_parts = ["m.deleted_at IS NULL", "m.date BETWEEN %s AND %s"]
            maint_params = [first_day, last_day]
            if vid:
                maint_where_parts.append("m.vehicle_id = %s")
                maint_params.append(str(vid))
            maint_where = "WHERE " + " AND ".join(maint_where_parts)

            cur.execute(
                '''
                SELECT vehicle_id, SUM(cost) AS total_cost
                FROM maintenance m
                '''
                + maint_where
                + '''
                GROUP BY vehicle_id
                ''',
                maint_params,
            )
            maint_summary = cur.fetchall()
            maint_by_vid = {r['vehicle_id']: r for r in maint_summary}

            return render_template('report.html',
                                   vehicles=vehicles,
                                   trip_summary=trip_summary,
                                   fuel_by_vid=fuel_by_vid,
                                   maint_by_vid=maint_by_vid,
                                   trip_entries=trip_entries,
                                   total_km=total_km,
                                   period_label=period_label,
                                   report_vehicle=report_vehicle,
                                   month_str=month_str,
                                   selected_vehicle=selected_vehicle,
                                   first_day=first_day,
                                   last_day=last_day)
        finally:
            cur.close()

    @app.route('/report/print/<int:vehicle_id>/<path:period>', endpoint='report_print')
    @login_required
    def report_print(vehicle_id, period):
        conn = get_db()
        cur = get_cursor(conn)
        try:
            cur.execute('SELECT * FROM vehicles WHERE id = %s', (vehicle_id,))
            vehicle = cur.fetchone()
            if not vehicle:
                abort(404)

            first_date, last_date, period_label = _parse_period(period)
            first_day = first_date.isoformat()
            last_day = last_date.isoformat()
            generated_on = date.today().isoformat()

            cur.execute(
                '''
                SELECT date, driver, purpose, odo_start, odo_end, notes
                FROM trips
                WHERE vehicle_id = %s
                  AND deleted_at IS NULL
                  AND date BETWEEN %s AND %s
                ORDER BY date, created_at
                ''',
                (vehicle_id, first_day, last_day),
            )
            trip_rows = cur.fetchall()

            rows = []
            total_km = 0
            for index, row in enumerate(trip_rows, start=1):
                trip_km = 0
                if row['odo_start'] is not None and row['odo_end'] is not None:
                    trip_km = row['odo_end'] - row['odo_start']
                total_km += trip_km
                rows.append({
                    'no': index,
                    'date': row['date'],
                    'driver': row['driver'],
                    'purpose': row['purpose'],
                    'odo_start': row['odo_start'] if row['odo_start'] is not None else '',
                    'odo_end': row['odo_end'] if row['odo_end'] is not None else '',
                    'trip_km': trip_km if trip_km else '',
                    'route_desc': row['purpose'],
                    'remarks': row['notes'] or '',
                })

            cur.execute(
                '''
                SELECT MAX(COALESCE(odo_end, odo_start)) AS km
                FROM trips
                WHERE vehicle_id = %s
                  AND deleted_at IS NULL
                  AND date < %s
                ''',
                (vehicle_id, first_day),
            )
            carry_row = cur.fetchone()
            carry_over = carry_row['km'] or 0
            period_total = carry_over + total_km
        finally:
            cur.close()

        return render_template(
            'print_vehicle_log.html',
            vehicle=vehicle,
            rows=rows,
            period_label=period_label,
            first_day=first_day,
            last_day=last_day,
            generated_on=generated_on,
            folio_sum=total_km,
            carry_over=carry_over,
            period_total=period_total,
        )
