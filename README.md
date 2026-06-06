# OSP Logbook

Wdrożenie w produkcji jest zgodne z Dockerfile i [render.yaml](render.yaml).

## Wymagania

- Python >= 3.12 (dev)
- PostgreSQL
- Redis (dla Flask-Limiter w produkcji)

## Konfiguracja

Przykładowe zmienne środowiskowe są w [.env.example](.env.example). Minimalny zestaw:

- `SECRET_KEY` — wymagany
- `DATABASE_URL` — wymagany
- `FLASK_ENV` — `development` | `production`
- `RATELIMIT_STORAGE_URI` — Redis w produkcji

## Uruchomienie (dev)

```bash
python run.py
```

## Uruchomienie (prod)

```bash
gunicorn app:app
```

## Testy

```bash
pytest tests/ --no-header -q
```

## Migracje bazy

Alembic + startowe `schema.sql`. Więcej w `alembic.ini` i `backend/db.py`.
