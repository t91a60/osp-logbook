from flask import Blueprint, request, session, redirect, url_for, flash, render_template
from werkzeug.security import check_password_hash
from backend.db import get_db, get_cursor

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'], endpoint='login')
def login():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute(
            'SELECT * FROM users WHERE username = %s', (username,)
        )
        user = cur.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['display_name'] = user['display_name']
            cur.close()
            return redirect(url_for('main.dashboard'))
        cur.close()
        flash('Nieprawidłowy login lub hasło.', 'error')
    return render_template('login.html')

@auth_bp.route('/logout', endpoint='logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))