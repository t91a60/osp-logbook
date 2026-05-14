from pathlib import Path
import os

import psycopg2
from psycopg2 import errors
import sqlparse


SCHEMA_VERSION = 10


def main() -> None:
    database_url = os.environ['DATABASE_URL']
    schema_path = Path(__file__).resolve().parent.parent / 'schema.sql'
    schema_sql = schema_path.read_text(encoding='utf-8')
    # Retry loop to handle Neon cold-start where compute is suspended and
    # the first connection attempt may fail or time out. Back off between
    # attempts to allow the DB to resume.
    max_attempts = 6
    backoff_seconds = 2
    for attempt in range(1, max_attempts + 1):
        try:
            connection = psycopg2.connect(database_url, connect_timeout=10)
            break
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            if attempt == max_attempts:
                raise
            print(f"DB connect attempt {attempt}/{max_attempts} failed: {exc}; retrying in {backoff_seconds}s")
            import time

            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)

    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            try:
                cursor.execute('SELECT COALESCE(MAX(version), 0) FROM schema_version;')
                current_version = int(cursor.fetchone()[0] or 0)
                if current_version >= SCHEMA_VERSION:
                    print(f"Schema already at version {current_version}; skipping bootstrap.")
                    return
            except errors.UndefinedTable:
                # schema_version doesn't exist yet — proceed to apply schema
                pass

            for statement in sqlparse.split(schema_sql):
                statement = statement.strip()
                if not statement:
                    continue
                try:
                    cursor.execute(statement)
                except errors.DuplicateTable:
                    # Someone else created the table concurrently — safe to ignore
                    continue
                except errors.UniqueViolation:
                    # INSERTs guarded by ON CONFLICT may still raise unique errors
                    # in rare race conditions; ignore and continue.
                    continue
                except errors.InsufficientPrivilege as exc:
                    # Some managed DBs disallow CREATE EXTENSION or similar; log and continue.
                    print(f"Permission error applying statement (ignored): {exc}")
                    continue
                except Exception:
                    # For any other error, re-raise to fail fast and surface the problem
                    raise
    finally:
        connection.close()


if __name__ == '__main__':
    main()