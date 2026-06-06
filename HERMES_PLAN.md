# Plan Poprawy OSP Logbook — etapy i zakres

Cel: doprowadzić aplikację do spójnego, produkcyjnego stanu 10/10 zgodnie z AGENTS.md i spełnić wymagania bezpieczeństwa, jakości kodu i DevOps.
Stan bieżący: mamy część roady, Security Headers, schemat SQL, testy, ale brakuje .dockerignore, GitHub Actions, pyproject/black/ruff/mypy, README, OpenAPI/Swagger, dedykowanych tendencji w testach i pełnego spojrzenia zewnętrznego na strukturę.

## Krok 1 — podstawy infrastrukturalne (repo, config, black/ruff)
- Dodaj .dockerignore z pełnym zestawem.
- Sprawdź, czy .gitignore zabezpiecza venv, pycache, coverage, .env, pyc.
- Dodaj pyproject.toml z [tool.black]/[tool.ruff]/[tool.mypy] i minimalną konfigurację.
- Uwzględnij wersje Python >=3.12, zgodne z Dockerfile/production.
- Zmiana ma być mała, ale stanowiąca podstawę reszty kroków.

## Krok 2 — testy i jakość (lint + test run)
- Przeanalizuj pytest/coverage i obecne testy po wprowadzeniu pyproject.
- Uruchom lokalnie pytest i poprawowe zależności.
- Ustaw baseline coverage, z dopisaniem hooków w docs.
- Stwórz testy regresji na bezpieczeństwo (CSRF, sesja, X-Frame-Options) — jeśli brakuje co najmniej jednego warunku wymaganego w AGENTS.md.

## Krok 3 — bezpieczeństwo (strukturalne uzupełnienia)
- Dołącz specyfikę CORS tam, gdzie wymagana jest komunikacja API z UI.
- Wkładamy config classy na staging (jeśli brak).
- Wymuś generowanie SECRET_KEY startowego w runtime environment zamiast hardcoded, z poziomu config.

## Krok 4 — DevOps
- Dodaj .github/workflows/test.yml + ci.yml (lint/build/test).
- Dodaj healthcheck,而死 backward-compat dla Render/Main.
- Dodawanie docker-compose.yml (dev) jeśli nie istnieje i jest zgodne z wymaganiem AGENTS.md.

## Krok 5 — dokumentacja API
- Dodaj endpointy Swagger/OpenAPI lub Redoc zgodnie z AGENTS.md.
- Dodaj README, zgodny z instalacją, env variables, endpointy API.

## Krok 6 — commit i branch
- Stwórz branch hermes-10-10-improvements i zumniejsz zmiany po każdym kroku, z commitami.
