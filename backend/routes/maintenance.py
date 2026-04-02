from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import date, timedelta
from backend.db import get_db, get_cursor
from backend.helpers import login_required, build_date_where, paginate, normalize_iso_date, parse_positive_int, db_tx
from backend.services.core_service import TripService
from backend.services.audit_service import AuditService

maintenance_bp = Blueprint('maintenance', __name__)

@maintenance_bp.route('/serwis', methods=['GET', 'POST'], endpoint='maintenance')
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

        cur.close()
        TripService.add_maintenance(
            vehicle_id=f['vehicle_id'],
            date_val=f['date'],
            odometer=f.get('odometer') or None,
            description=f['description'].strip(),
            cost=f.get('cost') or None,
            notes=f.get('notes', '').strip(),
            added_by=session['username'],
            status=status,
            priority=priority,
            due_date=f.get('due_date') or None,
        )
        flash('Wpis serwisowy zapisany.', 'success')
        return redirect(url_for('maintenance.maintenance',
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
    page = parse_positive_int(request.args.get('page'), default=1)

    where_parts = []
    params_list = []

    if selected_vehicle != 'all':
        where_parts.append('m.vehicle_id = %s')
        params_list.append(selected_vehicle)

    if selected_status == 'pending':
        where_parts.append("(m.status = 'pending' AND (m.due_date IS NULL OR m.due_date >= CURRENT_DATE))")
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
    count_sql = f'SELECT COUNT(*) AS count FROM maintenance m JOIN vehicles v ON m.vehicle_id = v.id {where_sql}'

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


@maintenance_bp.route('/serwis/<int:eid>/complete', methods=['POST'], endpoint='complete_maintenance')
@login_required
def complete_maintenance_view(eid):
    with db_tx() as (_, cur):
        cur.execute("UPDATE maintenance SET status = 'completed' WHERE id = %s", (eid,))

    AuditService.log('Edycja', 'Serwis', f"Zakończono serwis ID: {eid}")
    flash('Oznaczono jako wykonane.', 'success')
    return redirect(url_for('maintenance.maintenance'))


@maintenance_bp.route('/serwis/<int:eid>/next', methods=['POST'], endpoint='create_next_maintenance')
@login_required
def create_next_maintenance_view(eid):
    conn = get_db()
    with get_cursor(conn) as cur:
        cur.execute('''
            SELECT vehicle_id, odometer, description, notes, priority, due_date
            FROM maintenance
            WHERE id = %s
        ''', (eid,))
        row = cur.fetchone()

    if not row:
        flash('Nie znaleziono wpisu serwisowego.', 'error')
        return redirect(url_for('maintenance.maintenance'))

    due_date = normalize_iso_date(row['due_date'])
    if due_date:
        try:
            next_due = date.fromisoformat(due_date) + timedelta(days=90)
        except ValueError:
            next_due = date.today() + timedelta(days=90)
    else:
        next_due = date.today() + timedelta(days=90)

    with db_tx() as (_, cur):
        cur.execute('''
            INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            row['vehicle_id'],
            date.today(),
            row['odometer'],
            row['description'],
            None,
            row['notes'] or '',
            session['username'],
            'pending',
            row['priority'] or 'medium',
            next_due,
        ))

    AuditService.log('Dodanie', 'Serwis', f"Zaplanowano kolejny po serwisie ID: {eid}")
    flash('Dodano kolejny wpis serwisowy.', 'success')
    return redirect(url_for('maintenance.maintenance'))