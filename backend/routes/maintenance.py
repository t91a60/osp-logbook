from flask import render_template, request, flash, redirect, url_for, session
from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate

def register_routes(app):
    @app.route('/serwis', methods=['GET', 'POST'], endpoint='maintenance')
    @login_required
    def maintenance():
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('SELECT * FROM vehicles WHERE active = 1 ORDER BY name')
        vehicles = cur.fetchall()

        if request.method == 'POST':
            f = request.form
            priority = f.get('priority', 'medium')
            if priority not in ('low', 'medium', 'high'):
                priority = 'medium'

            status = f.get('status', 'pending')
            if status not in ('pending', 'completed'):
                status = 'pending'

            cur.execute('''
                INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                f['vehicle_id'], f['date'],
                f.get('odometer') or None,
                f['description'].strip(),
                f.get('cost') or None,
                f.get('notes', '').strip(),
                session['username'],
                status,
                priority,
                f.get('due_date') or None,
            ))
            conn.commit()
            flash('Wpis serwisowy zapisany.', 'success')
            cur.close()
            return redirect(url_for('maintenance',
                                    vehicle_id=request.args.get('vehicle_id', 'all'),
                                    status=request.args.get('status', 'all'),
                                    okres=request.args.get('okres', ''),
                                    od=request.args.get('od', ''),
                                    do=request.args.get('do', ''),
                                    page=1))

        selected_status = request.args.get('status', 'all')
        selected_vehicle = request.args.get('vehicle_id', 'all')
        okres = request.args.get('okres', '')
        od = request.args.get('od', '')
        do_ = request.args.get('do', '')
        page = int(request.args.get('page', 1))

        where_parts = []
        params_list = []

        if selected_vehicle != 'all':
            where_parts.append('m.vehicle_id = %s')
            params_list.append(selected_vehicle)

        if selected_status == 'pending':
            where_parts.append("(m.status = 'pending' AND (m.due_date IS NULL OR m.due_date >= CURRENT_DATE)) ")
        elif selected_status == 'completed':
            where_parts.append("m.status = 'completed'")
        elif selected_status == 'overdue':
            where_parts.append("(m.status = 'pending' AND m.due_date IS NOT NULL AND m.due_date < CURRENT_DATE)")

        date_parts, date_params = build_date_where(okres, od, do_, alias='m')
        where_parts += date_parts
        params_list += date_params

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

        base_sql = f'''
            SELECT m.*, v.name AS vname,
                   CASE
                       WHEN m.status = 'completed' THEN 'completed'
                       WHEN m.due_date IS NOT NULL AND m.due_date < CURRENT_DATE THEN 'overdue'
                       ELSE 'pending'
                   END AS effective_status
            FROM maintenance m
            JOIN vehicles v ON m.vehicle_id = v.id
            {where_sql}
            ORDER BY m.date DESC, m.created_at DESC
        '''
        count_sql = f'SELECT COUNT(*) FROM maintenance m JOIN vehicles v ON m.vehicle_id = v.id {where_sql}'

        entries, total, total_pages, page = paginate(
            conn, cur, count_sql, params_list, base_sql, params_list, page
        )
        cur.close()
        return render_template('maintenance.html',
                               vehicles=vehicles,
                               entries=entries,
                               today=date.today().isoformat(),
                               selected_status=selected_status,
                               selected_vehicle=selected_vehicle,
                               okres=okres, od=od, do_=do_,
                               page=page, total_pages=total_pages, total=total)


    @app.route('/serwis/<int:eid>/complete', methods=['POST'], endpoint='complete_maintenance')
    @login_required
    def complete_maintenance_view(eid):
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute("UPDATE maintenance SET status = 'completed' WHERE id = %s", (eid,))
        conn.commit()
        cur.close()
        flash('Oznaczono jako wykonane.', 'success')
        return redirect(url_for('maintenance'))


    @app.route('/serwis/<int:eid>/next', methods=['POST'], endpoint='create_next_maintenance')
    @login_required
    def create_next_maintenance_view(eid):
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            SELECT vehicle_id, odometer, description, notes, priority, due_date
            FROM maintenance
            WHERE id = %s
        ''', (eid,))
        row = cur.fetchone()

        if not row:
            cur.close()
            flash('Nie znaleziono wpisu serwisowego.', 'error')
            return redirect(url_for('maintenance'))

        if row['due_date']:
            try:
                next_due = (date.fromisoformat(row['due_date']) + timedelta(days=90)).isoformat()
            except ValueError:
                next_due = (date.today() + timedelta(days=90)).isoformat()
        else:
            next_due = (date.today() + timedelta(days=90)).isoformat()

        cur.execute('''
            INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            row['vehicle_id'],
            date.today().isoformat(),
            row['odometer'],
            row['description'],
            None,
            row['notes'] or '',
            session['username'],
            'pending',
            row['priority'] or 'medium',
            next_due,
        ))
        conn.commit()
        cur.close()
        flash('Dodano kolejny wpis serwisowy.', 'success')
        return redirect(url_for('maintenance'))