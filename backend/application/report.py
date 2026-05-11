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

from backend.db import get_db, get_cursor


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

    @staticmethod
    def execute(query: ReportQuery, vehicles: list[dict]) -> ReportResult:
        """Run all report queries and return a frozen ``ReportResult``.

        Args:
            query:    Input DTO specifying period and optional vehicle filter.
            vehicles: Pre-fetched vehicle list (typically from cache_service).
        """
        conn = get_db()
        cur = get_cursor(conn)
        try:
            return GenerateReportUseCase._load(cur, query, vehicles)
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(cur, query: ReportQuery, vehicles: list[dict]) -> ReportResult:
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
        trip_where = "WHERE t.date BETWEEN %s AND %s"
        trip_params: list = [first_day, last_day]
        if vid:
            trip_where += " AND t.vehicle_id = %s"
            trip_params.append(str(vid))

        cur.execute(f'''
            SELECT
                t.id, t.date, t.driver, t.purpose,
                t.odo_start, t.odo_end,
                t.time_start, t.time_end,
                t.notes, t.created_at,
                v.name AS vname
            FROM trips t JOIN vehicles v ON t.vehicle_id = v.id
            {trip_where}
            ORDER BY t.date, t.created_at
        ''', trip_params)
        trip_entries = list(cur.fetchall())

        # ── 2. Total km ─────────────────────────────────────────────────
        total_km_where = "WHERE date BETWEEN %s AND %s"
        total_km_params: list = [first_day, last_day]
        if vid:
            total_km_where += " AND vehicle_id = %s"
            total_km_params.append(vid)

        cur.execute(f'''
            SELECT COALESCE(SUM(
                CASE
                    WHEN odo_end IS NOT NULL AND odo_start IS NOT NULL
                        THEN odo_end - odo_start
                    ELSE 0
                END
            ), 0) AS total_km
            FROM trips
            {total_km_where}
        ''', total_km_params)
        total_km = cur.fetchone()['total_km']

        # ── 3. Trip summary per vehicle ─────────────────────────────────
        cur.execute(f'''
            SELECT v.id, v.name, v.plate,
                   COUNT(t.id) AS trip_count,
                   SUM(CASE WHEN t.odo_end IS NOT NULL AND t.odo_start IS NOT NULL
                            THEN t.odo_end - t.odo_start ELSE 0 END) AS total_km
            FROM vehicles v
            LEFT JOIN trips t
                ON t.vehicle_id = v.id
                AND t.date BETWEEN %s AND %s
                {"AND t.vehicle_id = %s" if vid else ""}
            GROUP BY v.id
            HAVING COUNT(t.id) > 0
            ORDER BY v.name
        ''', [first_day, last_day] + ([vid] if vid else []))
        trip_summary = list(cur.fetchall())

        # ── 4. Fuel summary ─────────────────────────────────────────────
        fuel_where = "WHERE f.date BETWEEN %s AND %s"
        fuel_params: list = [first_day, last_day]
        if vid:
            fuel_where += " AND f.vehicle_id = %s"
            fuel_params.append(str(vid))

        cur.execute(f'''
            SELECT vehicle_id,
                   SUM(liters) AS total_liters,
                   SUM(cost)   AS total_cost
            FROM fuel f
            {fuel_where}
            GROUP BY vehicle_id
        ''', fuel_params)
        fuel_by_vid: dict[int, dict] = {r['vehicle_id']: dict(r) for r in cur.fetchall()}

        # ── 5. Maintenance summary ──────────────────────────────────────
        maint_where = "WHERE m.date BETWEEN %s AND %s"
        maint_params: list = [first_day, last_day]
        if vid:
            maint_where += " AND m.vehicle_id = %s"
            maint_params.append(str(vid))

        cur.execute(f'''
            SELECT vehicle_id, SUM(cost) AS total_cost
            FROM maintenance m
            {maint_where}
            GROUP BY vehicle_id
        ''', maint_params)
        maint_by_vid: dict[int, dict] = {r['vehicle_id']: dict(r) for r in cur.fetchall()}

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
