from flask import Flask, session, request, abort, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
import secrets

from backend.config import get_config
from backend.db import register_db, check_db_health

def create_app(config_class=None):
    if config_class is None:
        config_class = get_config()

    # Crucial part: By using template_folder='.', we do not move the html files at all.
    app = Flask(__name__, template_folder='.')
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
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self';"
        
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
    from backend.routes import auth, main, trips, fuel, maintenance, admin, report, api
    auth.register_routes(app)
    main.register_routes(app)
    trips.register_routes(app)
    fuel.register_routes(app)
    maintenance.register_routes(app)
    admin.register_routes(app)
    report.register_routes(app)
    api.register_routes(app)

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
