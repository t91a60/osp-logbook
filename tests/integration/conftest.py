import pathlib

import psycopg2
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def redis_url(redis_container):
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer(
        "postgres:17-alpine",
        dbname="test_osp",
        username="test",
        password="test",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def pg_dsn(pg_container):
    return pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )


@pytest.fixture(scope="session", autouse=True)
def apply_schema(pg_dsn):
    schema_path = pathlib.Path(__file__).resolve().parents[2] / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn = psycopg2.connect(pg_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
    finally:
        conn.close()
