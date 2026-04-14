from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from backend.db import get_db, get_cursor
from backend.helpers import login_required, admin_required
from backend.services.audit_service import AuditService
from backend.services.cache_service import get_vehicles_cached

equipment_bp = Blueprint('equipment', __name__)

CATEGORIES = [
    'Sprzęt oddechowy',
    'Hydraulika',
    'Pilarstwo',
    'Ratownictwo medyczne',
    'Łączność',
    'Sprzęt wodny',
    'Agregaty',
    'Wyposażenie pojazdu',
    'Pozostałe',
]

# Domyślny inwentarz Fiata Ducato
DUCATO_EQUIPMENT = [
    ('Agregat prądotwórczy przenośny – 2,6 kW 230V GEKO AR1-90-B9', 1, 'szt', 'Agregaty'),
    ('Aparat powietrzny nadciśnieniowy DRAGER', 2, 'szt', 'Sprzęt oddechowy'),
    ('Butla do aparatu – 30MPa/6dm3 DRAGER', 2, 'szt', 'Sprzęt oddechowy'),
    ('Klucz do hydrantu podziemnego', 1, 'szt', 'Sprzęt wodny'),
    ('Tom wielofunkcyjny HOOLIGAN', 1, 'szt', 'Hydraulika'),
    ('Maska nadciśnieniowa DRAGER (02)', 1, 'szt', 'Sprzęt oddechowy'),
    ('Maska nadciśnieniowa DRAGER (03)', 1, 'szt', 'Sprzęt oddechowy'),
    ('Nożyce do prętów', 1, 'szt', 'Hydraulika'),
    ('Nożyce rozpieracz Kombi LUKAS SC350', 1, 'szt', 'Hydraulika'),
    ('Piła łańcuchowa STIHL MS 261', 1, 'szt', 'Pilarstwo'),
    ('Piła łańcuchowa STIHL MS 362', 1, 'szt', 'Pilarstwo'),
    ('Pompa hydrauliczna LUKAS P610', 1, 'szt', 'Hydraulika'),
    ('Prądownica wodna prosta – 200 dm3/min', 1, 'szt', 'Sprzęt wodny'),
    ('Radiotelefon – Przenośny PA_003', 1, 'szt', 'Łączność'),
    ('Radiotelefon – Przewoźny MA_002', 1, 'szt', 'Łączność'),
    ('Rozdzielacz kulowy', 1, 'szt', 'Sprzęt wodny'),
    ('Stojak hydrantowy', 1, 'szt', 'Sprzęt wodny'),
    ('Sygnalizator bezruchu MSA', 2, 'szt', 'Sprzęt oddechowy'),
    ('Tłumica', 1, 'szt', 'Sprzęt wodny'),
    ('Wąż tłoczny W-52', 1, 'szt', 'Sprzęt wodny'),
    ('Wąż tłoczny W-75', 1, 'szt', 'Sprzęt wodny'),
    ('Wysokociśnieniowy agregat gaśniczy wodny AW 65/40', 1, 'szt', 'Sprzęt wodny'),
    ('ZESTAW HYDRAULICZNY SPALINOWY', 1, 'szt', 'Hydraulika'),
    ('Zestaw PSP – R1', 1, 'szt', 'Ratownictwo medyczne'),
    ('Latarka kątowa', 1, 'szt', 'Łączność'),
    ('Latarka z nakładką do kierowania ruchem', 1, 'szt', 'Łączność'),
    ('Kamizelka KDR', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Gaśnica proszkowa', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Trójkąt ostrzegawczy', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Szperacz akumulatorowy', 1, 'szt', 'Łączność'),
    ('Nosze płachtowe', 1, 'szt', 'Ratownictwo medyczne'),
    ('Defibrylator AED', 1, 'szt', 'Ratownictwo medyczne'),
    ('Redukcja W110/W75', 1, 'szt', 'Sprzęt wodny'),
    ('Redukcja W75/W52', 1, 'szt', 'Sprzęt wodny'),
    ('Drabina składana', 1, 'szt', 'Pozostałe'),
    ('Pirometr', 1, 'szt', 'Ratownictwo medyczne'),
    ('Lizak do kierowania ruchem podświetlany', 1, 'szt', 'Łączność'),
    ('Piła kabłąkowa do drewna', 1, 'szt', 'Pilarstwo'),
    ('Maszt oświetleniowy 300/3', 1, 'szt', 'Agregaty'),
    ('Agregat AWP 6540', 1, 'szt', 'Agregaty'),
    ('Łopata', 1, 'szt', 'Pozostałe'),
    ('Sztychówka', 1, 'szt', 'Pozostałe'),
    ('Siekiera', 1, 'szt', 'Pozostałe'),
    ('Prądownica wodna TURBO', 1, 'szt', 'Sprzęt wodny'),
    ('Smok ssawny W10', 1, 'szt', 'Sprzęt wodny'),
    ('Linka ratownicza 20m', 1, 'szt', 'Ratownictwo medyczne'),
    ('Młotła', 1, 'szt', 'Pozostałe'),
    ('Piła ręczna do cięcia szyb', 1, 'szt', 'Pilarstwo'),
    ('Klucz wężowy', 1, 'szt', 'Sprzęt wodny'),
    ('Piła do metalu i stali STIHL TS 420', 1, 'szt', 'Pilarstwo'),
    ('Sorbent', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Koc (dywanik)', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Pachołek ostrzegawczy', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Parawan', 1, 'szt', 'Ratownictwo medyczne'),
    ('Podpora stabilizacyjna', 1, 'szt', 'Hydraulika'),
    ('Linka 1,6', 1, 'szt', 'Pozostałe'),
    ('Sintan 5 litrów', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Spodniobuty wędkarskie', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Peleryna przeciwdeszczowa', 1, 'szt', 'Wyposażenie pojazdu'),
    ('Zestaw TRIAGE', 1, 'szt', 'Ratownictwo medyczne'),
]


@equipment_bp.route('/sprzet')
@login_required
def equipment_list():
    conn = get_db()
    cur = get_cursor(conn)
    try:
        vid = request.args.get('vehicle_id', '')
        vehicles = get_vehicles_cached()

        eq_query = '''
            SELECT e.*, v.name AS vname
            FROM equipment e
            JOIN vehicles v ON e.vehicle_id = v.id
        '''
        params = []
        if vid:
            eq_query += ' WHERE e.vehicle_id = %s'
            params.append(vid)
        eq_query += ' ORDER BY v.name, e.category, e.name'

        cur.execute(eq_query, params)
        items = cur.fetchall()
    finally:
        cur.close()

    return render_template(
        'equipment.html',
        vehicles=vehicles,
        items=items,
        selected_vehicle=vid,
        categories=CATEGORIES,
    )


@equipment_bp.route('/sprzet/dodaj', methods=['POST'])
@admin_required
def equipment_add():
    f = request.form
    vehicle_id = f.get('vehicle_id', '').strip()
    name = f.get('name', '').strip()
    if not vehicle_id or not name:
        flash('Pojazd i nazwa sprzętu są wymagane.', 'error')
        return redirect(url_for('equipment.equipment_list'))

    category = f.get('category', 'Pozostałe').strip()
    if category not in CATEGORIES:
        category = 'Pozostałe'

    try:
        quantity = max(1, int(f.get('quantity', 1)))
    except (ValueError, TypeError):
        quantity = 1

    conn = get_db()
    cur = get_cursor(conn)
    try:
        cur.execute(
            'INSERT INTO equipment (vehicle_id, name, quantity, unit, category, notes) VALUES (%s,%s,%s,%s,%s,%s)',
            (vehicle_id, name, quantity, f.get('unit', 'szt').strip() or 'szt',
             category, f.get('notes', '').strip())
        )
        conn.commit()
        AuditService.log('Dodanie', 'Sprzęt', f'Pojazd ID: {vehicle_id}, Nazwa: {name}')
        flash('Sprzęt dodany.', 'success')
    finally:
        cur.close()
    return redirect(url_for('equipment.equipment_list', vehicle_id=vehicle_id))


@equipment_bp.route('/sprzet/<int:eid>/edytuj', methods=['GET', 'POST'])
@admin_required
def equipment_edit(eid):
    conn = get_db()
    cur = get_cursor(conn)
    try:
        cur.execute('SELECT e.*, v.name AS vname FROM equipment e JOIN vehicles v ON e.vehicle_id = v.id WHERE e.id = %s', (eid,))
        item = cur.fetchone()
        if not item:
            flash('Sprzęt nie istnieje.', 'error')
            return redirect(url_for('equipment.equipment_list'))

        if request.method == 'POST':
            f = request.form
            name = f.get('name', '').strip()
            category = f.get('category', 'Pozostałe').strip()
            if category not in CATEGORIES:
                category = 'Pozostałe'
            try:
                quantity = max(1, int(f.get('quantity', 1)))
            except (ValueError, TypeError):
                quantity = 1

            cur.execute(
                'UPDATE equipment SET name=%s, quantity=%s, unit=%s, category=%s, notes=%s WHERE id=%s',
                (name, quantity, f.get('unit', 'szt').strip() or 'szt',
                 category, f.get('notes', '').strip(), eid)
            )
            conn.commit()
            AuditService.log('Edycja', 'Sprzęt', f'ID: {eid}, Nazwa: {name}')
            flash('Sprzęt zaktualizowany.', 'success')
            return redirect(url_for('equipment.equipment_list', vehicle_id=item['vehicle_id']))

        vehicles = get_vehicles_cached()
    finally:
        cur.close()

    return render_template('equipment_edit.html', item=item, vehicles=vehicles, categories=CATEGORIES)


@equipment_bp.route('/sprzet/<int:eid>/usun', methods=['POST'])
@admin_required
def equipment_delete(eid):
    conn = get_db()
    cur = get_cursor(conn)
    try:
        cur.execute('SELECT vehicle_id, name FROM equipment WHERE id = %s', (eid,))
        item = cur.fetchone()
        if not item:
            flash('Sprzęt nie istnieje.', 'error')
            return redirect(url_for('equipment.equipment_list'))
        vid = item['vehicle_id']
        cur.execute('DELETE FROM equipment WHERE id = %s', (eid,))
        conn.commit()
        AuditService.log('Usunięcie', 'Sprzęt', f'ID: {eid}, Nazwa: {item["name"]}')
        flash('Sprzęt usunięty.', 'success')
    finally:
        cur.close()
    return redirect(url_for('equipment.equipment_list', vehicle_id=vid))


@equipment_bp.route('/sprzet/<int:eid>/preload', methods=['POST'])
@admin_required
def equipment_preload(eid):
    """Wgrywa domyślny inwentarz Ducato dla pojazdu o podanym ID."""
    conn = get_db()
    cur = get_cursor(conn)
    try:
        cur.execute('SELECT id FROM vehicles WHERE id = %s', (eid,))
        if not cur.fetchone():
            flash('Pojazd nie istnieje.', 'error')
            return redirect(url_for('equipment.equipment_list'))

        cur.execute('SELECT name FROM equipment WHERE vehicle_id = %s', (eid,))
        existing_names = {row['name'] for row in cur.fetchall()}

        to_insert = [
            (eid, name, qty, unit, cat)
            for name, qty, unit, cat in DUCATO_EQUIPMENT
            if name not in existing_names
        ]

        if to_insert:
            cur.executemany(
                'INSERT INTO equipment (vehicle_id, name, quantity, unit, category) VALUES (%s,%s,%s,%s,%s)',
                to_insert,
            )
        added = len(to_insert)

        conn.commit()
        AuditService.log('Dodanie', 'Sprzęt', f'Preload Ducato dla pojazdu ID: {eid}, dodano: {added} pozycji')
        flash(f'Dodano {added} pozycji sprzętu Ducato.', 'success')
    finally:
        cur.close()
    return redirect(url_for('equipment.equipment_list', vehicle_id=eid))


# API endpoint — używany przez formularz wyjazdu
@equipment_bp.route('/api/vehicle/<int:vid>/equipment')
@login_required
def api_vehicle_equipment(vid):
    conn = get_db()
    cur = get_cursor(conn)
    try:
        cur.execute(
            'SELECT id, name, quantity, unit, category FROM equipment WHERE vehicle_id = %s ORDER BY category, name',
            (vid,)
        )
        items = cur.fetchall()
    finally:
        cur.close()
    return jsonify([dict(r) for r in items])
