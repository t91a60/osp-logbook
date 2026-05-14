from pathlib import Path
import os

import psycopg2
import sqlparse


def main() -> None:
    database_url = os.environ['DATABASE_URL']
    schema_path = Path(__file__).resolve().parent.parent / 'schema.sql'
    schema_sql = schema_path.read_text(encoding='utf-8')

    connection = psycopg2.connect(database_url)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            for statement in sqlparse.split(schema_sql):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
    finally:
        connection.close()


if __name__ == '__main__':
    main()