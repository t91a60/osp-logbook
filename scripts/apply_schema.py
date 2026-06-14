#!/usr/bin/env python3
"""Apply schema and migrations to the database."""

import os
from pathlib import Path


def main() -> int:
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_URL")
    if not db_url:
        print("Brak DATABASE_URL/PG_URL — pomijam apply_schema")
        return 0

    try:
        import psycopg2  # noqa: F401
    except ImportError:
        print("Brak psycopg2 — pomijam apply_schema")
        return 0

    root = Path(__file__).resolve().parents[1]

    files = [
        root / "schema.sql",
        *sorted((root / "backend" / "migrations").glob("*.sql")),
    ]

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        for path in files:
            if not path.is_file():
                continue
            print(f"APPLY {path.relative_to(root)}")
            cur.execute(path.read_text(encoding="utf-8"))

        print("migrations applied")
        return 0
    except Exception as exc:
        print(f"apply_schema failed: {exc}")
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
