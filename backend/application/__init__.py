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

__all__ = [
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
