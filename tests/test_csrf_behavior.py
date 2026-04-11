from app import app


def _test_client_with_secret():
    app.config['SECRET_KEY'] = app.config.get('SECRET_KEY') or 'test-secret-key'
    return app.test_client()


def test_invalid_csrf_in_html_post_redirects_to_login():
    client = _test_client_with_secret()

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'expected-token'

    response = client.post('/login', data={'_csrf_token': 'wrong-token'})

    assert response.status_code == 302
    assert response.headers.get('Location', '').endswith('/login')


def test_invalid_csrf_in_ajax_post_returns_json_403():
    client = _test_client_with_secret()

    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'expected-token'

    response = client.post(
        '/login',
        data={'_csrf_token': 'wrong-token'},
        headers={'Accept': 'application/json'},
    )

    assert response.status_code == 403
    payload = response.get_json()
    assert payload is not None
    assert payload.get('success') is False
    assert payload.get('code') == 'csrf_invalid'
