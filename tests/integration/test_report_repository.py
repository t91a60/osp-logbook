import pytest
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.infrastructure.repositories.report import ReportRepository
from backend.services import cache_service


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def clear_report_cache():
    cache_service.cache._in_memory.clear()
    cache_service.invalidate_tags(["report"])
    yield
    cache_service.cache._in_memory.clear()
    cache_service.invalidate_tags(["report"])


@pytest.fixture
def seeded_db(pg_dsn):
    conn = psycopg2.connect(pg_dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM trip_equipment")
            cur.execute("DELETE FROM fuel")
            cur.execute("DELETE FROM maintenance")
            cur.execute("DELETE FROM trips")
            cur.execute("DELETE FROM equipment")
            cur.execute("DELETE FROM vehicles")

            cur.execute(
                "INSERT INTO vehicles (name, plate, type) VALUES (%s, %s, %s) RETURNING id",
                ("Fiat Ducato", "SBI001", "GBA"),
            )
            vehicle_id = cur.fetchone()[0]

            for day, km_s, km_e, driver in [
                ("2026-05-01", 37300, 37320, "Kowalski"),
                ("2026-05-10", 37320, 37345, "Nowak"),
                ("2026-05-20", 37345, 37360, "Kowalski"),
            ]:
                cur.execute(
                    """
                    INSERT INTO trips (vehicle_id, date, driver, odo_start, odo_end, purpose, added_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (vehicle_id, day, driver, km_s, km_e, "Akcja", "test"),
                )

            cur.execute(
                """
                INSERT INTO fuel (vehicle_id, date, driver, liters, cost, added_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (vehicle_id, "2026-05-15", "Nowak", 45.0, 290.0, "test"),
            )
            cur.execute(
                """
                INSERT INTO maintenance (vehicle_id, date, description, cost, added_by)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (vehicle_id, "2026-05-16", "Przegląd", 123.0, "test"),
            )
        conn.commit()
        yield {"vid": vehicle_id}
    finally:
        conn.close()


def test_get_trip_summary_returns_correct_totals(seeded_db, pg_dsn):
    repository = ReportRepository()
    vehicle_id = seeded_db["vid"]

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            result = repository.get_trip_summary(
                "2026-05-01", "2026-05-31", vehicle_id, cur=cur
            )

    assert len(result) == 1
    assert result[0]["trip_count"] == 3
    assert result[0]["total_km"] == 60


def test_get_fuel_summary_returns_correct_totals(seeded_db, pg_dsn):
    repository = ReportRepository()
    vehicle_id = seeded_db["vid"]

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            result = repository.get_fuel_summary(
                "2026-05-01", "2026-05-31", vehicle_id, cur=cur
            )

    assert vehicle_id in result
    assert abs(result[vehicle_id]["total_liters"] - 45.0) < 0.01
    assert abs(result[vehicle_id]["total_cost"] - 290.0) < 0.01


def test_get_trip_entries_returns_ordered_rows(seeded_db, pg_dsn):
    repository = ReportRepository()
    vehicle_id = seeded_db["vid"]

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            rows = repository.get_trip_entries(
                "2026-05-01", "2026-05-31", vehicle_id, cur=cur
            )

    assert len(rows) == 3
    dates = [r["date"].isoformat() if hasattr(r["date"], "isoformat") else r["date"] for r in rows]
    assert dates == sorted(dates)


def test_empty_period_returns_zero_totals(pg_dsn):
    repository = ReportRepository()

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            result = repository.get_trip_summary(
                "2025-01-01", "2025-01-31", 9999, cur=cur
            )

    assert result == []


def test_get_total_km_returns_zero_for_empty_period(pg_dsn):
    repository = ReportRepository()

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            total_km = repository.get_total_km(
                "2025-01-01", "2025-01-31", 9999, cur=cur
            )

    assert total_km == 0


def test_get_maintenance_summary_returns_totals(seeded_db, pg_dsn):
    repository = ReportRepository()
    vehicle_id = seeded_db["vid"]

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            result = repository.get_maintenance_summary(
                "2026-05-01", "2026-05-31", vehicle_id, cur=cur
            )

    assert vehicle_id in result
    assert abs(result[vehicle_id]["total_cost"] - 123.0) < 0.01


def test_run_with_cursor_uses_repo_db_helpers_when_cur_not_provided(pg_dsn, monkeypatch):
    repository = ReportRepository()
    conn = psycopg2.connect(pg_dsn)

    def fake_get_db():
        return conn

    def fake_get_cursor(db_conn):
        assert db_conn is conn
        return db_conn.cursor(cursor_factory=RealDictCursor)

    monkeypatch.setattr("backend.infrastructure.repositories.report.get_db", fake_get_db)
    monkeypatch.setattr("backend.infrastructure.repositories.report.get_cursor", fake_get_cursor)

    try:
        result = repository.get_trip_summary("2025-01-01", "2025-01-31", 9999)
        assert result == []
    finally:
        conn.close()
