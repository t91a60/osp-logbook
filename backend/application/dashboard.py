"""
GetDashboardUseCase — assembles the data for the main dashboard view.

Responsibilities:
  - Execute the optimised CTE query for vehicle cards (last_km, last_trip_date).
  - Fetch recent trips, recent fuel, and aggregate stats.
  - Compute days_since_last_trip per vehicle (pure Python, no SQL round-trip).
  - Return a structured DashboardResult dataclass; never raises Flask exceptions.

No Flask imports.  Uses get_db / get_cursor from backend.db.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from backend.db import get_db, get_cursor
from backend.helpers import normalize_iso_date


# ---------------------------------------------------------------------------
# Output DTO
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class VehicleCard:
    """Snapshot of a single vehicle for the dashboard card grid."""
    id: int
    name: str
    plate: str
    type: str
    last_km: int | None
    last_trip_date: str | None
    days_ago: int | None


@dataclass(slots=True, frozen=True)
class DashboardStats:
    trips: int
    fuel: int
    maintenance: int


@dataclass(slots=True, frozen=True)
class DashboardResult:
    """Return value of GetDashboardUseCase.execute()."""
    vehicle_cards: list[VehicleCard]
    recent_trips: list[dict[str, Any]]
    recent_fuel: list[dict[str, Any]]
    stats: DashboardStats
    generated_on: str          # ISO date string, e.g. "2026-05-12"


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class GetDashboardUseCase:
    """Assemble dashboard data in a single database round-trip (CTE).

    Usage::

        result = GetDashboardUseCase.execute()
        # result.vehicle_cards  → list[VehicleCard]
        # result.stats          → DashboardStats
        # result.recent_trips   → list[dict]
        # result.recent_fuel    → list[dict]

    The use case is intentionally a class with a single ``execute`` static
    method so it can be mocked easily in tests and extended with constructor
    DI later (e.g. inject a repository instead of calling get_db directly).
    """

    @staticmethod
    def execute() -> DashboardResult:
        """Run all dashboard queries and return a frozen ``DashboardResult``.

        All database access is contained in a single ``try/finally`` block
        that guarantees cursor closure regardless of errors.
        """
        conn = get_db()
        cur = get_cursor(conn)
        try:
            return GetDashboardUseCase._load(cur)
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(cur) -> DashboardResult:
        today = date.today()

        # ── 1. Vehicle cards — one CTE instead of N+1 queries ──────────
        cur.execute('''
            WITH trip_max AS (
                SELECT vehicle_id,
                       MAX(odo_end)  AS last_km,
                       MAX(date)     AS last_km_date
                FROM trips
                WHERE odo_end IS NOT NULL
                GROUP BY vehicle_id
            ),
            fuel_max AS (
                SELECT vehicle_id,
                       MAX(odometer) AS last_km,
                       MAX(date)     AS last_km_date
                FROM fuel
                WHERE odometer IS NOT NULL
                GROUP BY vehicle_id
            ),
            last_trip_date AS (
                SELECT vehicle_id, MAX(date) AS last_trip_date
                FROM trips
                GROUP BY vehicle_id
            )
            SELECT
                v.id, v.name, v.plate, v.type,
                CASE
                    WHEN tm.last_km IS NULL THEN fm.last_km
                    WHEN fm.last_km IS NULL THEN tm.last_km
                    WHEN (tm.last_km_date >= fm.last_km_date) THEN tm.last_km
                    ELSE fm.last_km
                END AS last_km,
                ltd.last_trip_date
            FROM vehicles v
            LEFT JOIN trip_max       tm  ON tm.vehicle_id = v.id
            LEFT JOIN fuel_max       fm  ON fm.vehicle_id = v.id
            LEFT JOIN last_trip_date ltd ON ltd.vehicle_id = v.id
            ORDER BY v.name
        ''')
        vehicle_cards = [
            GetDashboardUseCase._build_card(row, today)
            for row in cur.fetchall()
        ]

        # ── 2. Recent activity feeds ────────────────────────────────────
        cur.execute('''
            SELECT t.*, v.name AS vname
            FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
            ORDER BY t.date DESC, t.created_at DESC LIMIT 6
        ''')
        recent_trips = list(cur.fetchall())

        cur.execute('''
            SELECT f.*, v.name AS vname
            FROM fuel f JOIN vehicles v ON f.vehicle_id = v.id
            ORDER BY f.date DESC, f.created_at DESC LIMIT 4
        ''')
        recent_fuel = list(cur.fetchall())

        # ── 3. Aggregate stats ──────────────────────────────────────────
        cur.execute('''
            SELECT
                (SELECT COUNT(*) FROM trips)       AS trips_count,
                (SELECT COUNT(*) FROM fuel)        AS fuel_count,
                (SELECT COUNT(*) FROM maintenance) AS maint_count
        ''')
        row = cur.fetchone()
        stats = DashboardStats(
            trips=row['trips_count'],
            fuel=row['fuel_count'],
            maintenance=row['maint_count'],
        )

        return DashboardResult(
            vehicle_cards=vehicle_cards,
            recent_trips=recent_trips,
            recent_fuel=recent_fuel,
            stats=stats,
            generated_on=today.isoformat(),
        )

    @staticmethod
    def _build_card(row: dict, today: date) -> VehicleCard:
        """Convert a DB row dict to a typed VehicleCard with computed days_ago."""
        days_ago: int | None = None
        raw_date = row.get('last_trip_date')
        if raw_date:
            normalized = normalize_iso_date(raw_date)
            if normalized:
                try:
                    days_ago = (today - date.fromisoformat(normalized)).days
                except (TypeError, ValueError):
                    pass

        return VehicleCard(
            id=row['id'],
            name=row['name'],
            plate=row['plate'],
            type=row['type'],
            last_km=row['last_km'],
            last_trip_date=str(raw_date) if raw_date else None,
            days_ago=days_ago,
        )
