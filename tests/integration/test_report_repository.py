import pytest
import psycopg2

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
        conn.commit()
        yield {"vid": vehicle_id}
    finally:
        conn.close()


def test_get_trip_summary_returns_correct_totals(seeded_db, pg_dsn):
    repository = ReportRepository()
    vehicle_id = seeded_db["vid"]

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            rows = repository.get_trip_entries(
                "2026-05-01", "2026-05-31", vehicle_id, cur=cur
            )

    assert len(rows) == 3
    dates = [r["date"].isoformat() if hasattr(r["date"], "isoformat") else r["date"] for r in rows]
    assert dates == sorted(dates)


def test_empty_period_returns_zero_totals(pg_dsn):
    repository = ReportRepository()

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            result = repository.get_trip_summary(
                "2025-01-01", "2025-01-31", 9999, cur=cur
            )

    assert result == []


def test_get_total_km_returns_zero_for_empty_period(pg_dsn):
    repository = ReportRepository()

    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            total_km = repository.get_total_km(
                "2025-01-01", "2025-01-31", 9999, cur=cur
            )

    assert total_km == 0
