import os
from app import create_app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    use_https = app.config.get('USE_HTTPS', False)
    debug = app.config.get('DEBUG', True)

    print(f'\n🔥 Uruchamianie OSP Logbook w trybie DEWELOPERSKIM (port {port}, debug={debug})')
    print('   Do wdrożeń używaj Guniucorn (Render sam wykrywa app:app).\n')

    if use_https:
        cert_path = os.environ.get('OSP_SSL_CERT', 'cert.pem')
        key_path = os.environ.get('OSP_SSL_KEY', 'key.pem')
        if os.path.exists(cert_path) and os.path.exists(key_path):
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context=(cert_path, key_path))
        else:
            print('  HTTPS włączone: fallback do adhoc')
            app.run(host='0.0.0.0', port=port, debug=False, ssl_context='adhoc')
    else:
        app.run(host='0.0.0.0', port=port, debug=debug)
