"""
Application layer — Use Cases.

Use cases orchestrate:
  1. Input validation (via dataclass DTO)
  2. Repository calls (infrastructure layer)
  3. Side effects: audit logging, cache invalidation

Rules:
  - No Flask imports anywhere in this package.
  - No direct SQL / psycopg2 calls — use repositories.
  - Return plain dataclasses or dicts (no Flask Response objects).
"""
from .dashboard import GetDashboardUseCase, DashboardResult
from .report import GenerateReportUseCase, ReportQuery, ReportResult
from .trips import AddTripUseCase, AddTripCommand, GetTripsUseCase, GetTripsQuery


class UseCaseFactory:
    """Prosty kontener DI (Dependency Injection) dostarczający zmontowane przypadki użycia."""
    
    @staticmethod
    def get_dashboard_use_case() -> GetDashboardUseCase:
        from backend.infrastructure.repositories.dashboard import DashboardRepository
        repo = DashboardRepository()
        return GetDashboardUseCase(dashboard_repo=repo)

    @staticmethod
    def get_add_trip_use_case() -> AddTripUseCase:
        from backend.infrastructure.repositories.trips import TripRepository
        from backend.infrastructure.repositories.vehicles import VehicleRepository
        return AddTripUseCase(
            trip_repo=TripRepository(),
            vehicle_repo=VehicleRepository()
        )

    @staticmethod
    def get_trips_use_case() -> GetTripsUseCase:
        from backend.infrastructure.repositories.trips import TripRepository
        return GetTripsUseCase(trip_repo=TripRepository())

    @staticmethod
    def get_generate_report_use_case() -> GenerateReportUseCase:
        from backend.infrastructure.repositories.report import ReportRepository
        return GenerateReportUseCase(report_repo=ReportRepository())


__all__ = [
    # Factory
    "UseCaseFactory",
    # Dashboard
    "GetDashboardUseCase",
    "DashboardResult",
    # Report
    "GenerateReportUseCase",
    "ReportQuery",
    "ReportResult",
    # Trips
    "AddTripUseCase",
    "AddTripCommand",
    "GetTripsUseCase",
    "GetTripsQuery",
]
