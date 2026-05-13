"""
GenerateReportUseCase — queries and assembles monthly / quarterly vehicle reports.

Responsibilities:
  - Parse the period string (YYYY-MM or YYYY-Qn) into a date range.
  - Run 4 focused queries: trip entries, total km, trip summary per vehicle,
    fuel summary, maintenance summary.
  - Return a structured ReportResult dataclass.

No Flask imports.  _parse_period is extracted from routes/report.py (DRY).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from backend.infrastructure.repositories.protocols import ReportRepositoryProtocol


# ---------------------------------------------------------------------------
# Polish month names — pure data, no Flask dependency
# ---------------------------------------------------------------------------

_POLISH_MONTHS = [
    'styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec',
    'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień',
]


# ---------------------------------------------------------------------------
# Input DTO
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class ReportQuery:
    """Validated input for GenerateReportUseCase.

    Attributes:
        month_str:  Period string in format ``YYYY-MM`` or ``YYYY-Qn``.
                    An empty / invalid string falls back to the current month.
        vehicle_id: Optional positive integer to filter by vehicle.
                    ``0`` or ``None`` means all vehicles.
    """
    month_str: str = ""
    vehicle_id: int | None = None


# ---------------------------------------------------------------------------
# Output DTOs
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class ReportResult:
    """Return value of GenerateReportUseCase.execute()."""
    vehicles: list[dict[str, Any]]          # full vehicle list (for UI selector)
    trip_entries: list[dict[str, Any]]       # individual trip rows in range
    trip_summary: list[dict[str, Any]]       # per-vehicle trip counts + total km
    fuel_by_vid: dict[int, dict[str, Any]]  # vehicle_id → {total_liters, total_cost}
    maint_by_vid: dict[int, dict[str, Any]] # vehicle_id → {total_cost}
    total_km: int                            # sum of (odo_end - odo_start) across all trips
    period_label: str                        # human-readable label, e.g. "maj 2026"
    month_str: str                           # normalised YYYY-MM string for form state
    selected_vehicle: str                    # str(vehicle_id) or "" for all
    first_day: str                           # ISO date, inclusive range start
    last_day: str                            # ISO date, inclusive range end
    report_vehicle: dict[str, Any] | None   # full vehicle row if filtered, else None


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class GenerateReportUseCase:
    """Assemble report data for a given period and optional vehicle filter.

    Usage::

        query = ReportQuery(month_str="2026-05", vehicle_id=1)
        result = GenerateReportUseCase.execute(query, vehicles_list)

        # result.trip_entries  → list[dict]
        # result.total_km      → int
        # result.period_label  → "maj 2026"
    """

    def __init__(self, report_repo: ReportRepositoryProtocol):
        self._report_repo = report_repo

    def execute_instance(self, query: ReportQuery, vehicles: list[dict]) -> ReportResult:
        """Run all report queries and return a frozen ``ReportResult``.

        Args:
            query:    Input DTO specifying period and optional vehicle filter.
            vehicles: Pre-fetched vehicle list (typically from cache_service).
        """
        today = date.today()
        vid = query.vehicle_id or 0
        selected_vehicle = str(vid) if vid else ''

        # ── Parse period string ─────────────────────────────────────────
        month_str, first_day, last_day, period_label = _resolve_period(
            query.month_str, today
        )

        # ── Find the selected vehicle row for the template ──────────────
        report_vehicle = next(
            (v for v in vehicles if str(v['id']) == selected_vehicle), None
        )

        # ── 1. Trip entries ─────────────────────────────────────────────
        trip_entries = self._report_repo.get_trip_entries(first_day, last_day, vid)

        # ── 2. Total km ─────────────────────────────────────────────────
        total_km = self._report_repo.get_total_km(first_day, last_day, vid)

        # ── 3. Trip summary per vehicle ─────────────────────────────────
        trip_summary = self._report_repo.get_trip_summary(first_day, last_day, vid)

        # ── 4. Fuel summary ─────────────────────────────────────────────
        fuel_by_vid = self._report_repo.get_fuel_summary(first_day, last_day, vid)

        # ── 5. Maintenance summary ──────────────────────────────────────
        maint_by_vid = self._report_repo.get_maintenance_summary(first_day, last_day, vid)

        return ReportResult(
            vehicles=vehicles,
            trip_entries=trip_entries,
            trip_summary=trip_summary,
            fuel_by_vid=fuel_by_vid,
            maint_by_vid=maint_by_vid,
            total_km=total_km,
            period_label=period_label,
            month_str=month_str,
            selected_vehicle=selected_vehicle,
            first_day=first_day,
            last_day=last_day,
            report_vehicle=report_vehicle,
        )

    @classmethod
    def execute(cls, query: ReportQuery, vehicles: list[dict]) -> ReportResult:
        from backend.application import UseCaseFactory
        use_case = UseCaseFactory.get_generate_report_use_case()
        return use_case.execute_instance(query, vehicles)


# ---------------------------------------------------------------------------
# Period parsing — pure function, no I/O, fully testable in isolation
# ---------------------------------------------------------------------------

def _resolve_period(
    raw: str,
    today: date,
) -> tuple[str, str, str, str]:
    """Parse a period string and return (month_str, first_day, last_day, label).

    Supports two formats:
      - ``YYYY-MM``   → monthly period
      - ``YYYY-Qn``   → quarterly period (n ∈ {1, 2, 3, 4})

    Falls back to the current month on invalid input.

    Returns:
        month_str  – normalised canonical string for the period (``YYYY-MM`` or ``YYYY-Qn``)
        first_day  – ISO date string, e.g. ``"2026-05-01"``
        last_day   – ISO date string, e.g. ``"2026-05-31"``
        label      – Polish human label, e.g. ``"maj 2026"`` or ``"Q2 2026"``
    """
    period = (raw or '').strip()

    # ── Quarterly ───────────────────────────────────────────────────────
    if '-Q' in period:
        try:
            year_text, quarter_text = period.split('-Q', 1)
            year = int(year_text)
            quarter = int(quarter_text)
            if quarter not in (1, 2, 3, 4):
                raise ValueError
        except ValueError:
            year = today.year
            quarter = (today.month - 1) // 3 + 1

        start_month = (quarter - 1) * 3 + 1
        first_date = date(year, start_month, 1)
        if quarter == 4:
            last_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_date = date(year, start_month + 3, 1) - timedelta(days=1)
        label = f'Q{quarter} {year}'
        canonical = f'{year}-Q{quarter}'
        return canonical, first_date.isoformat(), last_date.isoformat(), label

    # ── Monthly ─────────────────────────────────────────────────────────
    try:
        year, month = int(period[:4]), int(period[5:7])
        first_date = date(year, month, 1)
        if month == 12:
            last_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_date = date(year, month + 1, 1) - timedelta(days=1)
        label = f'{_POLISH_MONTHS[month - 1]} {year}'
        canonical = period
        return canonical, first_date.isoformat(), last_date.isoformat(), label
    except (ValueError, IndexError):
        pass

    # ── Fallback: current month ─────────────────────────────────────────
    year, month = today.year, today.month
    first_date = today.replace(day=1)
    if month == 12:
        last_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_date = date(year, month + 1, 1) - timedelta(days=1)
    label = f'{_POLISH_MONTHS[month - 1]} {year}'
    canonical = today.strftime('%Y-%m')
    return canonical, first_date.isoformat(), last_date.isoformat(), label
