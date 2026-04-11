from flask import request, session, redirect, url_for, flash, render_template
from werkzeug.security import check_password_hash
from backend.db import get_db, get_cursor


def register_routes(app):
    # Import tutaj, żeby uniknąć circular import (app importuje routes, routes importuje app)
    from app import limiter

    @app.route('/login', methods=['GET', 'POST'], endpoint='login')
    @limiter.limit("10 per minute; 30 per hour", error_message="Zbyt wiele prób logowania. Spróbuj za chwilę.")
    def login():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            conn = get_db()
            cur = get_cursor(conn)
            try:
                cur.execute(
                    'SELECT id, username, password, display_name, is_admin FROM users WHERE username = %s',
                    (username,)
                )
                user = cur.fetchone()
            finally:
                cur.close()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['display_name'] = user['display_name']
                session['is_admin'] = bool(user['is_admin'])
                return redirect(url_for('dashboard'))

            flash('Nieprawidłowy login lub hasło.', 'error')
        return render_template('login.html')

    @app.route('/logout', endpoint='logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))
