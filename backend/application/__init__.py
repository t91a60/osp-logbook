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
from __future__ import annotations

# -- Dashboard ---------------------------------------------------------------
from .dashboard import GetDashboardUseCase, DashboardResult

# -- Report ------------------------------------------------------------------
from .report import GenerateReportUseCase, ReportQuery, ReportResult

# -- Trips -------------------------------------------------------------------
from .trips import AddTripUseCase, AddTripCommand, GetTripsUseCase, GetTripsQuery

# -- Fuel --------------------------------------------------------------------
from .fuel import (
    AddFuelUseCase, AddFuelCommand,
    EditFuelUseCase, EditFuelCommand,
    DeleteFuelUseCase, DeleteFuelCommand,
    GetFuelUseCase, GetFuelQuery,
    GetFuelByIdUseCase,
)

# -- Maintenance -------------------------------------------------------------
from .maintenance import (
    AddMaintenanceUseCase, AddMaintenanceCommand,
    EditMaintenanceUseCase, EditMaintenanceCommand,
    DeleteMaintenanceUseCase, DeleteMaintenanceCommand,
    GetMaintenanceUseCase, GetMaintenanceQuery,
    GetMaintenanceByIdUseCase,
    CompleteMaintenanceUseCase, CompleteMaintenanceCommand,
    CreateNextMaintenanceUseCase, CreateNextMaintenanceCommand,
)


class UseCaseFactory:
    """Jedyny kontener DI (Dependency Injection) tworzący instancje use case'ów.

    Zasady:
      - Tylko ta klasa tworzy instancje repozytoriów i use case'ów.
      - Trasy (routes) i testy mogą wywoływać `get_*_use_case()` lub
        przekazać własne mock-repo przy testowaniu.
      - Metody `get_*_repo()` są dostępne tylko dla zaawansowanych
        scenariuszy (np. admin route z wieloma repozytoriami).
    """

    # ── Repository factories ──────────────────────────────────────────────

    @staticmethod
    def get_dashboard_repo():
        from backend.infrastructure.repositories.dashboard import DashboardRepository
        return DashboardRepository()

    @staticmethod
    def get_report_repo():
        from backend.infrastructure.repositories.report import ReportRepository
        return ReportRepository()

    @staticmethod
    def get_trip_repo():
        from backend.infrastructure.repositories.trips import TripRepository
        return TripRepository()

    @staticmethod
    def get_vehicle_repo():
        from backend.infrastructure.repositories.vehicles import VehicleRepository
        return VehicleRepository()

    @staticmethod
    def get_fuel_repo():
        from backend.infrastructure.repositories.fuel import FuelRepository
        return FuelRepository()

    @staticmethod
    def get_maintenance_repo():
        from backend.infrastructure.repositories.maintenance import MaintenanceRepository
        return MaintenanceRepository()

    # ── Dashboard use cases ───────────────────────────────────────────────

    @staticmethod
    def get_dashboard_use_case() -> GetDashboardUseCase:
        return GetDashboardUseCase(dashboard_repo=UseCaseFactory.get_dashboard_repo())

    # ── Trip use cases ────────────────────────────────────────────────────

    @staticmethod
    def get_add_trip_use_case() -> AddTripUseCase:
        return AddTripUseCase(
            trip_repo=UseCaseFactory.get_trip_repo(),
            vehicle_repo=UseCaseFactory.get_vehicle_repo(),
        )

    @staticmethod
    def get_trips_use_case() -> GetTripsUseCase:
        return GetTripsUseCase(trip_repo=UseCaseFactory.get_trip_repo())

    # ── Report use cases ──────────────────────────────────────────────────

    @staticmethod
    def get_generate_report_use_case() -> GenerateReportUseCase:
        return GenerateReportUseCase(report_repo=UseCaseFactory.get_report_repo())

    # ── Fuel use cases ────────────────────────────────────────────────────

    @staticmethod
    def get_add_fuel_use_case() -> AddFuelUseCase:
        return AddFuelUseCase(
            fuel_repo=UseCaseFactory.get_fuel_repo(),
            vehicle_repo=UseCaseFactory.get_vehicle_repo(),
        )

    @staticmethod
    def get_edit_fuel_use_case() -> EditFuelUseCase:
        return EditFuelUseCase(
            fuel_repo=UseCaseFactory.get_fuel_repo(),
            vehicle_repo=UseCaseFactory.get_vehicle_repo(),
        )

    @staticmethod
    def get_delete_fuel_use_case() -> DeleteFuelUseCase:
        return DeleteFuelUseCase(fuel_repo=UseCaseFactory.get_fuel_repo())

    @staticmethod
    def get_fuel_list_use_case() -> GetFuelUseCase:
        return GetFuelUseCase(fuel_repo=UseCaseFactory.get_fuel_repo())

    @staticmethod
    def get_fuel_by_id_use_case() -> GetFuelByIdUseCase:
        return GetFuelByIdUseCase(fuel_repo=UseCaseFactory.get_fuel_repo())

    # ── Maintenance use cases ─────────────────────────────────────────────

    @staticmethod
    def get_add_maintenance_use_case() -> AddMaintenanceUseCase:
        return AddMaintenanceUseCase(
            maintenance_repo=UseCaseFactory.get_maintenance_repo(),
            vehicle_repo=UseCaseFactory.get_vehicle_repo(),
        )

    @staticmethod
    def get_edit_maintenance_use_case() -> EditMaintenanceUseCase:
        return EditMaintenanceUseCase(
            maintenance_repo=UseCaseFactory.get_maintenance_repo(),
            vehicle_repo=UseCaseFactory.get_vehicle_repo(),
        )

    @staticmethod
    def get_delete_maintenance_use_case() -> DeleteMaintenanceUseCase:
        return DeleteMaintenanceUseCase(
            maintenance_repo=UseCaseFactory.get_maintenance_repo()
        )

    @staticmethod
    def get_maintenance_list_use_case() -> GetMaintenanceUseCase:
        return GetMaintenanceUseCase(
            maintenance_repo=UseCaseFactory.get_maintenance_repo()
        )

    @staticmethod
    def get_maintenance_by_id_use_case() -> GetMaintenanceByIdUseCase:
        return GetMaintenanceByIdUseCase(
            maintenance_repo=UseCaseFactory.get_maintenance_repo()
        )

    @staticmethod
    def get_complete_maintenance_use_case() -> CompleteMaintenanceUseCase:
        return CompleteMaintenanceUseCase(
            maintenance_repo=UseCaseFactory.get_maintenance_repo()
        )

    @staticmethod
    def get_create_next_maintenance_use_case() -> CreateNextMaintenanceUseCase:
        return CreateNextMaintenanceUseCase(
            maintenance_repo=UseCaseFactory.get_maintenance_repo()
        )


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
    # Fuel
    "AddFuelUseCase",
    "AddFuelCommand",
    "EditFuelUseCase",
    "EditFuelCommand",
    "DeleteFuelUseCase",
    "DeleteFuelCommand",
    "GetFuelUseCase",
    "GetFuelQuery",
    "GetFuelByIdUseCase",
    # Maintenance
    "AddMaintenanceUseCase",
    "AddMaintenanceCommand",
    "EditMaintenanceUseCase",
    "EditMaintenanceCommand",
    "DeleteMaintenanceUseCase",
    "DeleteMaintenanceCommand",
    "GetMaintenanceUseCase",
    "GetMaintenanceQuery",
    "GetMaintenanceByIdUseCase",
    "CompleteMaintenanceUseCase",
    "CompleteMaintenanceCommand",
    "CreateNextMaintenanceUseCase",
    "CreateNextMaintenanceCommand",
]
