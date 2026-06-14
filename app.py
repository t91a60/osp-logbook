import os

from flask import Flask
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.bootstrap import ensure_bootstrap_admin
from backend.config import get_config
from backend.db import check_db_health, register_db
from backend.web import (
    configure_session_security,
    register_context_processors,
    register_error_handlers,
    register_request_guards,
    register_security_headers,
)

_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    """Return the application-wide Limiter instance.

    Routes call ``get_limiter()`` instead of importing ``limiter`` directly,
    avoiding circular imports and the fragile module-level overwrite pattern.
    """
    global _limiter
    if _limiter is None:
        _limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[],
            storage_uri='memory://',
        )
    return _limiter


def create_app(config_class=None):
    if config_class is None:
        config_class = get_config()

    app = Flask(__name__, template_folder='templates')
    app.config.from_object(config_class)
    Compress(app)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY environment variable is not set.')
    if not app.config.get('DATABASE_URL'):
        raise RuntimeError('DATABASE_URL environment variable is not set.')

    is_production = os.environ.get('FLASK_ENV', 'development') == 'production'
    ratelimit_storage_uri = (os.environ.get('RATELIMIT_STORAGE_URI') or '').strip()
    if is_production:
        if not ratelimit_storage_uri:
            raise RuntimeError(
                'RATELIMIT_STORAGE_URI environment variable is required in production.'
            )
        if ratelimit_storage_uri == 'memory://':
            raise RuntimeError('RATELIMIT_STORAGE_URI must use Redis backend in production.')
    if not ratelimit_storage_uri:
        ratelimit_storage_uri = 'memory://'

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    global _limiter
    _limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[],
        storage_uri=ratelimit_storage_uri,
    )
    _limiter.init_app(app)
    configure_session_security(app)
    register_request_guards(app)
    register_context_processors(app)
    register_security_headers(app)
    register_error_handlers(app)

    register_db(app)
    ensure_bootstrap_admin(app)

    @app.route('/health', endpoint='health')
    def health():
        if check_db_health():
            return 'OK', 200
        return 'DB ERROR', 500

    from backend.routes import admin, api, auth, fuel, logs, main, maintenance, report, trips
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
            print(f'\n  OSP Logbook dziala na https://0.0.0.0:{port}')
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context=(cert_path, key_path))
        else:
            print(
                '\n  HTTPS wlaczone, ale brak plikow cert.pem/key.pem '
                '– uruchamiam certyfikat ad-hoc.'
            )
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context='adhoc')
    else:
        print(f'\n  OSP Logbook dziala na http://0.0.0.0:{port} (DEBUG={debug})')
        app.run(host='0.0.0.0', port=port, debug=debug)
