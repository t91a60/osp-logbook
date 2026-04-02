# Etap budowy
FROM python:3.11-slim-bullseye AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Środowisko docelowe
FROM python:3.11-slim-bullseye
WORKDIR /app
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN apt-get update && apt-get install -y libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache /wheels/*

COPY . /app
ENV FLASK_ENV=production

EXPOSE 5000
CMD ["gunicorn", "-w", "2", "--bind", "0.0.0.0:5000", "app:app"]
