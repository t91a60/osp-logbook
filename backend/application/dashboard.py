"""
GetDashboardUseCase — assembles the data for the main dashboard view.

Responsibilities:
  - Orchestrate data fetching using DashboardRepository.
  - Compute days_since_last_trip per vehicle (pure Python).
  - Return a structured DashboardResult dataclass.

No Flask imports. No direct SQL calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.helpers import normalize_iso_date
from backend.infrastructure.repositories.dashboard import DashboardRepository


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
    """Return value of GetDashboardUseCase."""
    vehicle_cards: list[VehicleCard]
    recent_trips: list[dict[str, Any]]
    recent_fuel: list[dict[str, Any]]
    stats: DashboardStats
    generated_on: str          # ISO date string, e.g. "2026-05-12"


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class GetDashboardUseCase:
    """Assemble dashboard data using injected repositories.
    """

    def __init__(self, dashboard_repo: DashboardRepository):
        self._repo = dashboard_repo

    def execute_instance(self) -> DashboardResult:
        """Run all dashboard queries via repository and return a frozen ``DashboardResult``."""
        today = date.today()

        # 1. Vehicle cards
        raw_cards = self._repo.get_vehicle_cards()
        vehicle_cards = [
            self._build_card(row, today) for row in raw_cards
        ]

        # 2. Recent activity feeds
        recent_trips = self._repo.get_recent_trips(limit=6)
        recent_fuel = self._repo.get_recent_fuel(limit=4)

        # 3. Aggregate stats
        stats_data = self._repo.get_aggregate_stats()
        stats = DashboardStats(**stats_data)

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

    @classmethod
    def execute(cls) -> DashboardResult:
        """
        Legacy adapter dla kompatybilności wstecznej (aby nie ruszać istniejących wywołań w routes).
        Używa UseCaseFactory do wstrzyknięcia zależności.
        """
        from backend.application import UseCaseFactory
        
        use_case = UseCaseFactory.get_dashboard_use_case()
        return use_case.execute_instance()

