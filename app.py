import os
import hmac
from datetime import datetime, timezone

from flask import Flask, session, request, abort, url_for, g, jsonify, redirect, flash, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets

from backend.config import get_config
from backend.db import register_db, check_db_health
from backend.bootstrap import ensure_bootstrap_admin

# Globalna instancja limitera — trasy importują ją przez `from app import limiter`
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)


def create_app(config_class=None):
    if config_class is None:
        config_class = get_config()

    app = Flask(__name__, template_folder='templates')
    app.config.from_object(config_class)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY environment variable is not set.')
    if not app.config.get('DATABASE_URL'):
        raise RuntimeError('DATABASE_URL environment variable is not set.')

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    limiter.init_app(app)

    def _is_json_request():
        if request.is_json:
            return True
        accept = (request.headers.get('Accept') or '').lower()
        xrw = (request.headers.get('X-Requested-With') or '').lower()
        return 'application/json' in accept or xrw == 'xmlhttprequest'

    def _csrf_failure_response():
        message = 'Sesja wygasła lub token CSRF jest niepoprawny. Odśwież stronę i spróbuj ponownie.'
        if _is_json_request():
            return jsonify({'success': False, 'message': message, 'code': 'csrf_invalid'}), 403

        flash(message, 'error')
        if 'user_id' in session:
            return redirect(request.referrer or url_for('dashboard'))
        return redirect(url_for('login'))

    @app.before_request
    def csrf_protect():
        g.csp_nonce = secrets.token_urlsafe(16)
        if request.endpoint not in {'login', 'logout', 'health', 'static'}:
            last_seen = session.get('session_started_at')
            if 'user_id' in session and last_seen:
                try:
                    started_at = datetime.fromisoformat(last_seen)
                    lifetime = app.config.get('PERMANENT_SESSION_LIFETIME')
                    ttl_seconds = lifetime.total_seconds() if lifetime else 8 * 3600
                    age_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
                    if age_seconds > ttl_seconds:
                        session.clear()
                        flash('Sesja wygasła. Zaloguj się ponownie.', 'error')
                        return redirect(url_for('login'))
                except (TypeError, ValueError):
                    session.clear()
                    return redirect(url_for('login'))

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            token = session.get('_csrf_token')
            req_token = (
                request.form.get('_csrf_token')
                or request.form.get('csrf_token')
                or request.headers.get('X-CSRFToken')
                or request.headers.get('X-CSRF-Token')
                or request.headers.get('X-XSRF-TOKEN')
            )

            if not token or not req_token:
                return _csrf_failure_response()

            if not hmac.compare_digest(str(token), str(req_token)):
                return _csrf_failure_response()

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            if '_csrf_token' not in session:
                session['_csrf_token'] = secrets.token_hex(32)
            return session['_csrf_token']

        def asset_url(filename):
            return url_for('static', filename=filename)

        def csp_nonce():
            return getattr(g, 'csp_nonce', '')

        return dict(csrf_token=generate_csrf_token, asset_url=asset_url, csp_nonce=csp_nonce)

    @app.after_request
    def add_security_headers(response):
        nonce = getattr(g, 'csp_nonce', '')
        script_src = "script-src 'self' 'unsafe-inline'"
        if nonce:
            script_src = f"{script_src} 'nonce-{nonce}'"

        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response.headers['Content-Security-Policy'] = (
            f"default-src 'self'; {script_src}; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
            "base-uri 'self'; frame-ancestors 'none';"
        )
        if app.debug:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception('Unhandled application error')
        if request.path.startswith('/api/'):
            return jsonify({'ok': False, 'error': 'Internal server error'}), 500
        return render_template(
            'error.html',
            title='Błąd serwera',
            message='Wystąpił nieoczekiwany błąd. Spróbuj ponownie za chwilę.',
        ), 500

    register_db(app)
    ensure_bootstrap_admin(app)

    @app.route('/health', endpoint='health')
    def health():
        if check_db_health():
            return 'OK', 200
        return 'DB ERROR', 500

    from backend.routes import auth, main, trips, fuel, maintenance, admin, report, api, logs
    auth.register_routes(app)
    main.register_routes(app)
    trips.register_routes(app)
    fuel.register_routes(app)
    maintenance.register_routes(app)
    admin.register_routes(app)
    report.register_routes(app)
    api.register_routes(app)
    app.register_blueprint(logs.logs_bp)

    from backend.routes.equipment import equipment_bp
    from backend.routes.more import more_bp
    app.register_blueprint(equipment_bp)
    app.register_blueprint(more_bp)

    return app


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
        app.run(host='0.0.0.0', port=port, debug=debug)
