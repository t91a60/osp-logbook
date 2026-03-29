"""
OSP Logbook - Dziennik Pojazdów Straży Pożarnej
Prosta, lokalna aplikacja do ewidencji pojazdów.
v2 – 2025: last-km hint, driver autocomplete, trip-purpose combo,
           monthly report, pagination, date filter, toast notifications,
           vehicle cards on dashboard.
"""

import sqlite3
import os
from datetime import date, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='.')
app.secret_key = os.environ.get('SECRET_KEY', 'osp-logbook-secret-zmien-to')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

USE_HTTPS = os.environ.get('OSP_USE_HTTPS', '0') == '1'
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=USE_HTTPS,
)
if USE_HTTPS:
    app.config['PREFERRED_URL_SCHEME'] = 'https'

DB_PATH = os.path.join(os.path.dirname(__file__), 'logbook.db')

PAGE_SIZE = 50


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            display_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT NOT NULL,
            plate  TEXT DEFAULT '',
            type   TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS trips (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            date       TEXT NOT NULL,
            driver     TEXT NOT NULL,
            odo_start  INTEGER,
            odo_end    INTEGER,
            purpose    TEXT NOT NULL,
            notes      TEXT DEFAULT '',
            added_by   TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS fuel (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            date       TEXT NOT NULL,
            driver     TEXT NOT NULL,
            odometer   INTEGER,
            liters     REAL NOT NULL,
            cost       REAL,
            notes      TEXT DEFAULT '',
            added_by   TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS maintenance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id  INTEGER NOT NULL REFERENCES vehicles(id),
            date        TEXT NOT NULL,
            odometer    INTEGER,
            description TEXT NOT NULL,
            cost        REAL,
            notes       TEXT DEFAULT '',
            added_by    TEXT DEFAULT '',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Lightweight schema migration for maintenance workflow enhancements.
    columns = {
        row['name'] for row in conn.execute("PRAGMA table_info(maintenance)").fetchall()
    }
    if 'status' not in columns:
        conn.execute("ALTER TABLE maintenance ADD COLUMN status TEXT DEFAULT 'pending'")
    if 'priority' not in columns:
        conn.execute("ALTER TABLE maintenance ADD COLUMN priority TEXT DEFAULT 'medium'")
    if 'due_date' not in columns:
        conn.execute("ALTER TABLE maintenance ADD COLUMN due_date TEXT")

    # Default admin if no users exist
    if not conn.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        conn.execute(
            'INSERT INTO users (username, password, display_name) VALUES (?, ?, ?)',
            ('admin', generate_password_hash('admin123'), 'Administrator')
        )
        conn.commit()

    conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_date_where(okres, od, do_, alias='t'):
    """Return (where_clause_str, params_list) for date filtering."""
    today = date.today()
    parts = []
    params = []

    if okres == 'ten':
        first = today.replace(day=1).isoformat()
        last = today.isoformat()
        parts.append(f"{alias}.date BETWEEN ? AND ?")
        params += [first, last]
    elif okres == 'poprzedni':
        first_this = today.replace(day=1)
        last_prev = (first_this - timedelta(days=1)).isoformat()
        first_prev = (first_this - timedelta(days=1)).replace(day=1).isoformat()
        parts.append(f"{alias}.date BETWEEN ? AND ?")
        params += [first_prev, last_prev]
    elif od or do_:
        if od:
            parts.append(f"{alias}.date >= ?")
            params.append(od)
        if do_:
            parts.append(f"{alias}.date <= ?")
            params.append(do_)

    return parts, params


def _paginate(conn, count_sql, count_params, data_sql, data_params, page):
    """Return (entries, total_count, total_pages)."""
    total = conn.execute(count_sql, count_params).fetchone()[0]
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PAGE_SIZE
    entries = conn.execute(
        data_sql + f" LIMIT {PAGE_SIZE} OFFSET {offset}", data_params
    ).fetchall()
    return entries, total, total_pages, page


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['display_name'] = user['display_name']
            return redirect(url_for('dashboard'))
        flash('Nieprawidłowy login lub hasło.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    vehicles_raw = conn.execute(
        'SELECT * FROM vehicles WHERE active = 1 ORDER BY name'
    ).fetchall()

    # Build vehicle cards with last_km + last_trip_date
    vehicle_cards = []
    for v in vehicles_raw:
        vid = v['id']
        # Last km: MAX(odo_end) from trips vs MAX(odometer) from fuel
        trip_row = conn.execute(
            "SELECT MAX(odo_end) as km, MAX(date) as dt FROM trips WHERE vehicle_id = ? AND odo_end IS NOT NULL",
            (vid,)
        ).fetchone()
        fuel_row = conn.execute(
            "SELECT MAX(odometer) as km, MAX(date) as dt FROM fuel WHERE vehicle_id = ? AND odometer IS NOT NULL",
            (vid,)
        ).fetchone()

        trip_km = trip_row['km'] if trip_row and trip_row['km'] else None
        fuel_km = fuel_row['km'] if fuel_row and fuel_row['km'] else None
        trip_dt = trip_row['dt'] if trip_row else None
        fuel_dt = fuel_row['dt'] if fuel_row else None

        # Pick whichever date is newer for km
        last_km = None
        if trip_km is not None and fuel_km is not None:
            last_km = trip_km if (trip_dt or '') >= (fuel_dt or '') else fuel_km
        elif trip_km is not None:
            last_km = trip_km
        elif fuel_km is not None:
            last_km = fuel_km

        # Last trip date
        last_trip_row = conn.execute(
            "SELECT MAX(date) as dt FROM trips WHERE vehicle_id = ?", (vid,)
        ).fetchone()
        last_trip_dt = last_trip_row['dt'] if last_trip_row else None

        days_ago = None
        if last_trip_dt:
            try:
                delta = date.today() - date.fromisoformat(last_trip_dt)
                days_ago = delta.days
            except ValueError:
                pass

        vehicle_cards.append({
            'id': v['id'],
            'name': v['name'],
            'plate': v['plate'],
            'type': v['type'],
            'last_km': last_km,
            'last_trip_date': last_trip_dt,
            'days_ago': days_ago,
        })

    recent_trips = conn.execute('''
        SELECT t.*, v.name AS vname
        FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
        ORDER BY t.date DESC, t.created_at DESC LIMIT 6
    ''').fetchall()
    recent_fuel = conn.execute('''
        SELECT f.*, v.name AS vname
        FROM fuel f JOIN vehicles v ON f.vehicle_id = v.id
        ORDER BY f.date DESC, f.created_at DESC LIMIT 4
    ''').fetchall()
    stats = dict(
        trips=conn.execute('SELECT COUNT(*) FROM trips').fetchone()[0],
        fuel=conn.execute('SELECT COUNT(*) FROM fuel').fetchone()[0],
        maintenance=conn.execute('SELECT COUNT(*) FROM maintenance').fetchone()[0],
    )
    conn.close()
    return render_template('dashboard.html',
                           vehicles=vehicles_raw,
                           vehicle_cards=vehicle_cards,
                           recent_trips=recent_trips,
                           recent_fuel=recent_fuel,
                           stats=stats,
                           today=date.today().isoformat())


# ── Trips ─────────────────────────────────────────────────────────────────────

@app.route('/wyjazdy', methods=['GET', 'POST'])
@login_required
def trips():
    conn = get_db()
    vehicles = conn.execute(
        'SELECT * FROM vehicles WHERE active = 1 ORDER BY name'
    ).fetchall()

    if request.method == 'POST':
        f = request.form
        # Combo purpose: if 'Inne (wpisz ręcznie)' pick custom_purpose
        purpose_sel = f.get('purpose_select', '').strip()
        if purpose_sel == '__inne__':
            purpose = f.get('purpose_custom', '').strip()
        else:
            purpose = purpose_sel or f.get('purpose', '').strip()

        conn.execute('''
            INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            f.get('odo_start') or None, f.get('odo_end') or None,
            purpose, f.get('notes', '').strip(),
            session['username']
        ))
        conn.commit()
        flash('Wyjazd zapisany.', 'success')
        conn.close()
        return redirect(url_for('trips',
                                vehicle_id=f.get('vehicle_id', ''),
                                okres=request.args.get('okres', ''),
                                od=request.args.get('od', ''),
                                do=request.args.get('do', ''),
                                page=1))

    vid = request.args.get('vehicle_id', '')
    okres = request.args.get('okres', '')
    od = request.args.get('od', '')
    do_ = request.args.get('do', '')
    page = int(request.args.get('page', 1))

    where_parts = []
    params = []

    if vid:
        where_parts.append('t.vehicle_id = ?')
        params.append(vid)

    date_parts, date_params = _build_date_where(okres, od, do_, alias='t')
    where_parts += date_parts
    params += date_params

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

    base_sql = f'''
        SELECT t.*, v.name AS vname FROM trips t
        JOIN vehicles v ON t.vehicle_id = v.id
        {where_sql}
        ORDER BY t.date DESC, t.created_at DESC
    '''
    count_sql = f'SELECT COUNT(*) FROM trips t JOIN vehicles v ON t.vehicle_id = v.id {where_sql}'

    entries, total, total_pages, page = _paginate(
        conn, count_sql, params, base_sql, params, page
    )

    # auto-open add form if ?add=1
    add_open = request.args.get('add', '') == '1'

    conn.close()
    return render_template('trips.html',
                           vehicles=vehicles,
                           entries=entries,
                           today=date.today().isoformat(),
                           selected_vehicle=vid,
                           okres=okres, od=od, do_=do_,
                           page=page, total_pages=total_pages, total=total,
                           add_open=add_open)


# ── Fuel ──────────────────────────────────────────────────────────────────────

@app.route('/tankowania', methods=['GET', 'POST'])
@login_required
def fuel():
    conn = get_db()
    vehicles = conn.execute(
        'SELECT * FROM vehicles WHERE active = 1 ORDER BY name'
    ).fetchall()

    if request.method == 'POST':
        f = request.form
        conn.execute('''
            INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            f.get('odometer') or None,
            f['liters'], f.get('cost') or None,
            f.get('notes', '').strip(), session['username']
        ))
        conn.commit()
        flash('Tankowanie zapisane.', 'success')
        conn.close()
        return redirect(url_for('fuel',
                                vehicle_id=f.get('vehicle_id', ''),
                                okres=request.args.get('okres', ''),
                                od=request.args.get('od', ''),
                                do=request.args.get('do', ''),
                                page=1))

    vid = request.args.get('vehicle_id', '')
    okres = request.args.get('okres', '')
    od = request.args.get('od', '')
    do_ = request.args.get('do', '')
    page = int(request.args.get('page', 1))

    where_parts = []
    params = []

    if vid:
        where_parts.append('f.vehicle_id = ?')
        params.append(vid)

    date_parts, date_params = _build_date_where(okres, od, do_, alias='f')
    where_parts += date_parts
    params += date_params

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

    base_sql = f'''
        SELECT f.*, v.name AS vname FROM fuel f
        JOIN vehicles v ON f.vehicle_id = v.id
        {where_sql}
        ORDER BY f.date DESC, f.created_at DESC
    '''
    count_sql = f'SELECT COUNT(*) FROM fuel f JOIN vehicles v ON f.vehicle_id = v.id {where_sql}'

    entries, total, total_pages, page = _paginate(
        conn, count_sql, params, base_sql, params, page
    )

    add_open = request.args.get('add', '') == '1'

    conn.close()
    return render_template('fuel.html',
                           vehicles=vehicles,
                           entries=entries,
                           today=date.today().isoformat(),
                           selected_vehicle=vid,
                           okres=okres, od=od, do_=do_,
                           page=page, total_pages=total_pages, total=total,
                           add_open=add_open)


# ── Maintenance ───────────────────────────────────────────────────────────────

@app.route('/serwis', methods=['GET', 'POST'])
@login_required
def maintenance():
    conn = get_db()
    vehicles = conn.execute(
        'SELECT * FROM vehicles WHERE active = 1 ORDER BY name'
    ).fetchall()

    if request.method == 'POST':
        f = request.form
        priority = f.get('priority', 'medium')
        if priority not in ('low', 'medium', 'high'):
            priority = 'medium'

        status = f.get('status', 'pending')
        if status not in ('pending', 'completed'):
            status = 'pending'

        conn.execute('''
            INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        conn.close()
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
        where_parts.append('m.vehicle_id = ?')
        params_list.append(selected_vehicle)

    if selected_status == 'pending':
        where_parts.append("(m.status = 'pending' AND (m.due_date IS NULL OR m.due_date >= date('now'))) ")
    elif selected_status == 'completed':
        where_parts.append("m.status = 'completed'")
    elif selected_status == 'overdue':
        where_parts.append("(m.status = 'pending' AND m.due_date IS NOT NULL AND m.due_date < date('now'))")

    date_parts, date_params = _build_date_where(okres, od, do_, alias='m')
    where_parts += date_parts
    params_list += date_params

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

    base_sql = f'''
        SELECT m.*, v.name AS vname,
               CASE
                   WHEN m.status = 'completed' THEN 'completed'
                   WHEN m.due_date IS NOT NULL AND m.due_date < date('now') THEN 'overdue'
                   ELSE 'pending'
               END AS effective_status
        FROM maintenance m
        JOIN vehicles v ON m.vehicle_id = v.id
        {where_sql}
        ORDER BY m.date DESC, m.created_at DESC
    '''
    count_sql = f'SELECT COUNT(*) FROM maintenance m JOIN vehicles v ON m.vehicle_id = v.id {where_sql}'

    entries, total, total_pages, page = _paginate(
        conn, count_sql, params_list, base_sql, params_list, page
    )
    conn.close()
    return render_template('maintenance.html',
                           vehicles=vehicles,
                           entries=entries,
                           today=date.today().isoformat(),
                           selected_status=selected_status,
                           selected_vehicle=selected_vehicle,
                           okres=okres, od=od, do_=do_,
                           page=page, total_pages=total_pages, total=total)


@app.route('/serwis/<int:eid>/complete', methods=['POST'])
@login_required
def complete_maintenance(eid):
    conn = get_db()
    conn.execute("UPDATE maintenance SET status = 'completed' WHERE id = ?", (eid,))
    conn.commit()
    conn.close()
    flash('Oznaczono jako wykonane.', 'success')
    return redirect(url_for('maintenance'))


@app.route('/serwis/<int:eid>/next', methods=['POST'])
@login_required
def create_next_maintenance(eid):
    conn = get_db()
    row = conn.execute('''
        SELECT vehicle_id, odometer, description, notes, priority, due_date
        FROM maintenance
        WHERE id = ?
    ''', (eid,)).fetchone()

    if not row:
        conn.close()
        flash('Nie znaleziono wpisu serwisowego.', 'error')
        return redirect(url_for('maintenance'))

    if row['due_date']:
        try:
            next_due = (date.fromisoformat(row['due_date']) + timedelta(days=90)).isoformat()
        except ValueError:
            next_due = (date.today() + timedelta(days=90)).isoformat()
    else:
        next_due = (date.today() + timedelta(days=90)).isoformat()

    conn.execute('''
        INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    conn.close()
    flash('Dodano kolejny wpis serwisowy.', 'success')
    return redirect(url_for('maintenance'))


# ── Vehicles ──────────────────────────────────────────────────────────────────

@app.route('/pojazdy', methods=['GET', 'POST'])
@login_required
def vehicles():
    conn = get_db()
    if request.method == 'POST':
        f = request.form
        conn.execute(
            'INSERT INTO vehicles (name, plate, type) VALUES (?, ?, ?)',
            (f['name'].strip(), f.get('plate', '').strip(), f.get('type', '').strip())
        )
        conn.commit()
        flash('Pojazd dodany.', 'success')
        conn.close()
        return redirect(url_for('vehicles'))

    vlist = conn.execute(
        'SELECT * FROM vehicles ORDER BY active DESC, name'
    ).fetchall()
    conn.close()
    return render_template('vehicles.html', vehicles=vlist)


@app.route('/pojazdy/<int:vid>/toggle', methods=['POST'])
@login_required
def toggle_vehicle(vid):
    conn = get_db()
    v = conn.execute('SELECT active FROM vehicles WHERE id = ?', (vid,)).fetchone()
    if v:
        conn.execute('UPDATE vehicles SET active = ? WHERE id = ?',
                     (0 if v['active'] else 1, vid))
        conn.commit()
    conn.close()
    return redirect(url_for('vehicles'))


# ── Users ─────────────────────────────────────────────────────────────────────

@app.route('/uzytkownicy', methods=['GET', 'POST'])
@login_required
def users():
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            pw = request.form.get('password', '')
            if len(pw) < 4:
                flash('Hasło musi mieć co najmniej 4 znaki.', 'error')
            else:
                try:
                    conn.execute(
                        'INSERT INTO users (username, password, display_name) VALUES (?, ?, ?)',
                        (request.form['username'].strip(),
                         generate_password_hash(pw),
                         request.form['display_name'].strip())
                    )
                    conn.commit()
                    flash('Użytkownik dodany.', 'success')
                except sqlite3.IntegrityError:
                    flash('Login już istnieje.', 'error')
        elif action == 'change_pw':
            uid = request.form.get('uid')
            new_pw = request.form.get('new_password', '')
            if uid and len(new_pw) >= 4:
                conn.execute('UPDATE users SET password = ? WHERE id = ?',
                             (generate_password_hash(new_pw), uid))
                conn.commit()
                flash('Hasło zmienione.', 'success')
            else:
                flash('Hasło musi mieć co najmniej 4 znaki.', 'error')
        conn.close()
        return redirect(url_for('users'))

    all_users = conn.execute(
        'SELECT id, username, display_name FROM users ORDER BY display_name'
    ).fetchall()
    conn.close()
    return render_template('users.html', users=all_users)


# ── Delete ────────────────────────────────────────────────────────────────────

@app.route('/usun/<string:kind>/<int:eid>', methods=['POST'])
@login_required
def delete_entry(kind, eid):
    tables = {'wyjazd': 'trips', 'tankowanie': 'fuel', 'serwis': 'maintenance'}
    table = tables.get(kind)
    if table:
        conn = get_db()
        conn.execute(f'DELETE FROM {table} WHERE id = ?', (eid,))
        conn.commit()
        conn.close()
        flash('Wpis usunięty.', 'success')
    referrer = request.referrer or url_for('dashboard')
    return redirect(referrer)


# ── Monthly Report ─────────────────────────────────────────────────────────────

@app.route('/raport')
@login_required
def report():
    conn = get_db()
    today = date.today()
    # Default: current month
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

    vehicles = conn.execute(
        'SELECT * FROM vehicles ORDER BY active DESC, name'
    ).fetchall()

    # Trip list for the month
    trip_where = "WHERE t.date BETWEEN ? AND ?"
    trip_params = [first_day, last_day]
    if vid:
        trip_where += " AND t.vehicle_id = ?"
        trip_params.append(vid)

    trip_entries = conn.execute(f'''
        SELECT t.*, v.name AS vname
        FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
        {trip_where}
        ORDER BY t.date, t.created_at
    ''', trip_params).fetchall()

    # Summary per vehicle: total km, fuel L, service cost
    summary_where = "WHERE t.date BETWEEN ? AND ?"
    summary_params = [first_day, last_day]
    if vid:
        summary_where += " AND t.vehicle_id = ?"
        summary_params.append(vid)

    trip_summary = conn.execute(f'''
        SELECT v.id, v.name, v.plate,
               COUNT(t.id) AS trip_count,
               SUM(CASE WHEN t.odo_end IS NOT NULL AND t.odo_start IS NOT NULL
                        THEN t.odo_end - t.odo_start ELSE 0 END) AS total_km
        FROM vehicles v
        LEFT JOIN trips t ON t.vehicle_id = v.id AND t.date BETWEEN ? AND ?
        {"AND t.vehicle_id = ?" if vid else ""}
        GROUP BY v.id
        HAVING trip_count > 0
        ORDER BY v.name
    ''', [first_day, last_day] + ([vid] if vid else [])).fetchall()

    fuel_where = "WHERE f.date BETWEEN ? AND ?"
    fuel_params = [first_day, last_day]
    if vid:
        fuel_where += " AND f.vehicle_id = ?"
        fuel_params.append(vid)

    fuel_summary = conn.execute(f'''
        SELECT vehicle_id, SUM(liters) AS total_liters, SUM(cost) AS total_cost
        FROM fuel f
        {fuel_where}
        GROUP BY vehicle_id
    ''', fuel_params).fetchall()
    fuel_by_vid = {r['vehicle_id']: r for r in fuel_summary}

    maint_where = "WHERE m.date BETWEEN ? AND ?"
    maint_params = [first_day, last_day]
    if vid:
        maint_where += " AND m.vehicle_id = ?"
        maint_params.append(vid)

    maint_summary = conn.execute(f'''
        SELECT vehicle_id, SUM(cost) AS total_cost
        FROM maintenance m
        {maint_where}
        GROUP BY vehicle_id
    ''', maint_params).fetchall()
    maint_by_vid = {r['vehicle_id']: r for r in maint_summary}

    conn.close()
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


# ── AJAX API ──────────────────────────────────────────────────────────────────

@app.route('/api/vehicle/<int:vid>/last_km')
@login_required
def api_vehicle_last_km(vid):
    """Return last known odometer reading for a vehicle."""
    conn = get_db()
    trip_row = conn.execute(
        "SELECT MAX(odo_end) as km, MAX(date) as dt FROM trips WHERE vehicle_id = ? AND odo_end IS NOT NULL",
        (vid,)
    ).fetchone()
    fuel_row = conn.execute(
        "SELECT MAX(odometer) as km, MAX(date) as dt FROM fuel WHERE vehicle_id = ? AND odometer IS NOT NULL",
        (vid,)
    ).fetchone()
    conn.close()

    trip_km = trip_row['km'] if trip_row and trip_row['km'] else None
    fuel_km = fuel_row['km'] if fuel_row and fuel_row['km'] else None
    trip_dt = trip_row['dt'] if trip_row and trip_row['dt'] else None
    fuel_dt = fuel_row['dt'] if fuel_row and fuel_row['dt'] else None

    # Pick the newer reading
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

    days_ago = None
    if dt:
        try:
            days_ago = (date.today() - date.fromisoformat(dt)).days
        except ValueError:
            pass

    return jsonify({'km': km, 'date': dt, 'days_ago': days_ago})


@app.route('/api/drivers')
@login_required
def api_drivers():
    """Return unique driver names from last 90 days, sorted."""
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    conn = get_db()
    rows = conn.execute('''
        SELECT DISTINCT driver FROM (
            SELECT driver FROM trips WHERE date >= ?
            UNION
            SELECT driver FROM fuel WHERE date >= ?
        ) ORDER BY driver ASC
    ''', (cutoff, cutoff)).fetchall()
    conn.close()
    return jsonify([r['driver'] for r in rows])


@app.route('/api/trips', methods=['POST'])
@login_required
def api_add_trip():
    """AJAX endpoint for fast trip entry (no page reload)."""
    try:
        f = request.form
        purpose_sel = f.get('purpose_select', '').strip()
        if purpose_sel == '__inne__':
            purpose = f.get('purpose_custom', '').strip()
        else:
            purpose = purpose_sel or f.get('purpose', '').strip()

        conn = get_db()
        conn.execute('''
            INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, notes, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            f.get('odo_start') or None, f.get('odo_end') or None,
            purpose, f.get('notes', '').strip(),
            session['username']
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '✓ Wyjazd zapisany'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd: {str(e)}'}), 400


@app.route('/api/fuel', methods=['POST'])
@login_required
def api_add_fuel():
    """AJAX endpoint for fast fuel entry (no page reload)."""
    try:
        f = request.form
        liters = (f.get('liters') or '').strip()
        if not liters:
            return jsonify({'success': False, 'message': 'Podaj ilość paliwa.'}), 400
        conn = get_db()
        conn.execute('''
            INSERT INTO fuel (vehicle_id, date, driver, odometer, liters, cost, notes, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f['vehicle_id'], f['date'], f['driver'].strip(),
            f.get('odometer') or None,
            liters, f.get('cost') or None,
            f.get('notes', '').strip(), session['username']
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '✓ Tankowanie zapisane'})
    except Exception as e:
        app.logger.exception('Fuel API error: %s', e)
        return jsonify({'success': False, 'message': 'Nie udało się zapisać tankowania. Spróbuj ponownie.'}), 400


@app.route('/api/maintenance', methods=['POST'])
@login_required
def api_add_maintenance():
    """AJAX endpoint for fast maintenance entry (no page reload)."""
    try:
        f = request.form
        priority = f.get('priority', 'medium')
        if priority not in ('low', 'medium', 'high'):
            priority = 'medium'

        status = f.get('status', 'pending')
        if status not in ('pending', 'completed'):
            status = 'pending'

        conn = get_db()
        conn.execute('''
            INSERT INTO maintenance (vehicle_id, date, odometer, description, cost, notes, added_by, status, priority, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        conn.close()
        return jsonify({'success': True, 'message': '✓ Wpis serwisowy zapisany'})
    except Exception as e:
        app.logger.exception('Maintenance API error: %s', e)
        return jsonify({'success': False, 'message': 'Nie udało się zapisać wpisu serwisowego. Spróbuj ponownie.'}), 400


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    if USE_HTTPS:
        cert_path = os.environ.get('OSP_SSL_CERT', 'cert.pem')
        key_path = os.environ.get('OSP_SSL_KEY', 'key.pem')
        if os.path.exists(cert_path) and os.path.exists(key_path):
            print(f'\n  OSP Logbook działa na https://0.0.0.0:{port}')
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context=(cert_path, key_path))
        else:
            print('\n  HTTPS włączone, ale brak plików cert.pem/key.pem – uruchamiam certyfikat ad-hoc.')
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context='adhoc')
    else:
        print(f'\n  OSP Logbook działa na http://0.0.0.0:{port}')
        print(f'  Domyślne konto: admin / admin123\n')
        app.run(host='0.0.0.0', port=port, debug=False)
