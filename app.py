import os
import hashlib
from flask import Flask, session, request, abort, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
import secrets

from backend.config import get_config
from backend.db import register_db, check_db_health

def create_app(config_class=None):
    if config_class is None:
        config_class = get_config()

    # Removed template_folder='.' hack
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Rejestracja globalnych funkcji (CSRF)
    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            # API can have custom csrf logic but here we check it
            token = session.get('_csrf_token', None)
            if not token or token != request.form.get('_csrf_token'):
                abort(403, 'Błąd walidacji żądania (niepoprawny token CSRF).')


    @app.context_processor
    def inject_statics():
        def get_hashed_static(filename):
            filepath = os.path.join(app.root_path, 'static', filename)
            if os.path.exists(filepath):
                mtime = int(os.path.getmtime(filepath))
                return f"/{filename}?v={mtime}" # Wait, flask static files are at /static/... by default? URL expects it.
                # Actually it is better to provide the correct static path. But the prompt said `asset_url` replacing `url_for`.
                # If we use `url_for('static', filename='...v=mtime')` it's better. But let's follow the prompt. Actually the prompt says:
                # `return f"/static/{filename}?v={mtime}"`
                return f"/static/{filename}?v={mtime}"
            return f"/static/{filename}"
            
        return dict(asset_url=get_hashed_static)

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            if '_csrf_token' not in session:
                session['_csrf_token'] = secrets.token_hex(32)
            return session['_csrf_token']
        return dict(csrf_token=generate_csrf_token)

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self';"
        
        # The FIX to caching dev environment / sw.js missing updates
        if app.debug:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    register_db(app)

    @app.route('/health', endpoint='health')
    def health():
        if check_db_health():
            return 'OK', 200
        return 'DB ERROR', 500

    # Routes registering
    from backend.routes.auth import auth_bp
    from backend.routes.main import main_bp
    from backend.routes.trips import trips_bp
    from backend.routes.fuel import fuel_bp
    from backend.routes.maintenance import maintenance_bp
    from backend.routes.admin import admin_bp
    from backend.routes.report import report_bp
    from backend.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(fuel_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error

        app.logger.exception('Nieobsłużony wyjątek aplikacji: %s', error)

        if request.path.startswith('/api/'):
            return {'ok': False, 'error': 'Wystąpił błąd serwera. Spróbuj ponownie.'}, 500

        return render_template('error.html',
                               title='Wystąpił problem',
                               message='Wystąpił nieoczekiwany błąd. Spróbuj ponownie za chwilę.'), 500

    return app

# Gunicorn lub standardowy import backend:
app = create_app()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    use_https = app.config.get('USE_HTTPS', False)
    debug = app.config.get('DEBUG', True)

    if use_https:
        cert_path = os.environ.get('OSP_SSL_CERT', 'cert.pem')
        key_path = os.environ.get('OSP_SSL_KEY', 'key.pem')
        if os.path.exists(cert_path) and os.path.exists(key_path):
            print(f'\n  OSP Logbook działa na https://0.0.0.0:{port}')
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context=(cert_path, key_path))
        else:
            print('\n  HTTPS włączone, ale brak plików cert.pem/key.pem – uruchamiam certyfikat ad-hoc.')
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context='adhoc')
    else:
        print(f'\n  OSP Logbook działa na http://0.0.0.0:{port} (DEBUG={debug})')
        print(f'  Domyślne konto: admin / admin123\n')
        app.run(host='0.0.0.0', port=port, debug=debug)
