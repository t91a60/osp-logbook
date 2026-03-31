# OSP Logbook

![Wersja](https://img.shields.io/badge/Wersja-2.1-ff6b3d)
![Tech](https://img.shields.io/badge/Tech-Python%20%7C%20Flask%20%7C%20PostgreSQL-blue)
![Licencja](https://img.shields.io/badge/Licencja-MIT-success)

OSP Logbook to dziennik pojazdow dla OSP: wyjazdy, tankowania, serwis i raporty miesieczne.
Projekt jest lekki, mobilny i gotowy do uruchomienia lokalnie albo w chmurze (Render).

## Najwazniejsze funkcje

- Ewidencja wyjazdow (pojazd, kierowca, cel, licznik)
- Ewidencja paliwa (ilosc, koszt, historia)
- Ksiazka serwisowa (terminy, wykonanie, historia)
- Raport miesieczny (sumy i zestawienia)
- Panel administracyjny i zarzadzanie uzytkownikami

## Wymagania

- Python 3.11+
- pip
- Baza danych: SQLite lokalnie (domyslnie)
- Baza danych: PostgreSQL na produkcji (np. Render)

## Szybki start lokalnie

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Aplikacja domyslnie startuje na `http://localhost:5000`.

## Uruchomienie produkcyjne

Do produkcji uzywaj Gunicorn:

```bash
gunicorn app:app
```

Render uruchamia aplikacje komenda `gunicorn app:app` i ustawia port automatycznie przez `PORT`.

## Zmienne srodowiskowe

- `PORT` - port HTTP (domyslnie 5000 lokalnie)
- `FLASK_ENV` - tryb srodowiska
- `DATABASE_URL` - URL do PostgreSQL (produkcyjnie)
- `SECRET_KEY` - klucz sesji (wymagany na produkcji)
- `OSP_USE_HTTPS=1` - lokalny tryb HTTPS
- `OSP_SSL_CERT`, `OSP_SSL_KEY` - certyfikat i klucz przy lokalnym HTTPS

## Healthcheck

Endpoint zdrowia aplikacji:

- `GET /health` -> `200 OK` gdy aplikacja i DB dzialaja

## Diagnostyka bledow 500

Jesli pojawia sie `Internal Server Error`:

1. Sprawdz logi deployu (Render -> Logs).
2. Zweryfikuj `DATABASE_URL` i dostep do bazy.
3. Sprawdz, czy migracje/struktura tabel sa aktualne.
4. Przetestuj endpoint `GET /health`.
5. Dla tras API sprawdz odpowiedz JSON z komunikatem bledu.

Aplikacja ma globalny handler wyjatkow:

- API zwraca bezpieczny JSON bledu.
- Widoki HTML zwracaja strone bledu zamiast surowego stack trace.

## Znane uwagi wdrozeniowe

- PostgreSQL jest bardziej rygorystyczny niz SQLite (typy dat, GROUP BY/HAVING).
- Przy zmianach SQL zawsze testuj scenariusze raportu i serwisu na tej samej bazie, ktora jest na produkcji.

## Struktura projektu

```text
app.py
backend/
	config.py
	db.py
	helpers.py
	routes/
static/
*.html
requirements.txt
```

## Rozwoj i kontrybucje

Pull requesty mile widziane. Przy wiekszych zmianach dodaj:

- opis problemu,
- kroki testowe,
- informacje o kompatybilnosci SQLite/PostgreSQL.

## Licencja

Projekt jest na licencji MIT.
