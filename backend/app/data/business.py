"""'Sessions overview' business KPIs - the same numbers as the old Looker
Studio dashboard (Total Sessions / Assessment / Practice, MTD, last month,
YoY%), now read from the dbt-materialized `v_dialogs_business_daily_dashboard`
table instead of the slow hand-built view it used to query directly.
"""

from collections import defaultdict
from datetime import date, timedelta

from app.bq import run_query
from app.cache import ttl_cache
from app.config import get_settings
from app.data.mock_store import get_store

PRODUCTION_GROUPS = {"assessment", "practice"}


def get_business_overview(date_from: str, date_to: str) -> dict:
    settings = get_settings()
    daily_rows = get_store().business_daily if settings.use_mock_data else _fetch_daily()
    return _summarize(daily_rows, date_from, date_to)


@ttl_cache
def _fetch_daily() -> list[dict]:
    settings = get_settings()
    return run_query(
        f"SELECT CAST(started_date AS STRING) AS started_date, dashboard_group, dialogs "
        f"FROM `{settings.reports_ref}.v_dialogs_business_daily_dashboard`"
    )


def _shift_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29 with no matching leap day
        return d.replace(month=2, day=28, year=d.year - years)


def _yoy_pct(current: int, previous: int) -> float | None:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def _summarize(daily_rows: list[dict], date_from: str, date_to: str) -> dict:
    by_key: dict[tuple[str, str], int] = defaultdict(int)
    for r in daily_rows:
        by_key[(r["started_date"][:10], r["dashboard_group"])] += r["dialogs"]

    def sum_range(d_from: str, d_to: str, groups: set[str]) -> int:
        return sum(c for (d, g), c in by_key.items() if g in groups and d_from <= d <= d_to)

    today = date.today()
    month_start = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    mtd_from, mtd_to = month_start.isoformat(), today.isoformat()
    mtd_ly_from, mtd_ly_to = _shift_years(month_start, 1).isoformat(), _shift_years(today, 1).isoformat()
    last_month_from, last_month_to = last_month_start.isoformat(), last_month_end.isoformat()
    last_month_ly_from = _shift_years(last_month_start, 1).isoformat()
    last_month_ly_to = _shift_years(last_month_end, 1).isoformat()

    mtd_total = sum_range(mtd_from, mtd_to, PRODUCTION_GROUPS)
    mtd_assessment = sum_range(mtd_from, mtd_to, {"assessment"})
    mtd_practice = sum_range(mtd_from, mtd_to, {"practice"})
    mtd_total_ly = sum_range(mtd_ly_from, mtd_ly_to, PRODUCTION_GROUPS)
    mtd_assessment_ly = sum_range(mtd_ly_from, mtd_ly_to, {"assessment"})
    mtd_practice_ly = sum_range(mtd_ly_from, mtd_ly_to, {"practice"})

    last_month_total = sum_range(last_month_from, last_month_to, PRODUCTION_GROUPS)
    last_month_total_ly = sum_range(last_month_ly_from, last_month_ly_to, PRODUCTION_GROUPS)

    daily_series: dict[str, dict[str, int]] = defaultdict(lambda: {"assessment": 0, "practice": 0, "test": 0})
    for (d, g), c in by_key.items():
        if date_from <= d <= date_to:
            daily_series[d][g] = daily_series[d].get(g, 0) + c

    return {
        "tiles": {
            "total_sessions": sum_range(date_from, date_to, PRODUCTION_GROUPS),
            "total_assessment_sessions": sum_range(date_from, date_to, {"assessment"}),
            "total_practice_sessions": sum_range(date_from, date_to, {"practice"}),
            "mtd_sessions": mtd_total,
            "mtd_sessions_yoy_pct": _yoy_pct(mtd_total, mtd_total_ly),
            "mtd_assessment_sessions": mtd_assessment,
            "mtd_assessment_sessions_yoy_pct": _yoy_pct(mtd_assessment, mtd_assessment_ly),
            "mtd_practice_sessions": mtd_practice,
            "mtd_practice_sessions_yoy_pct": _yoy_pct(mtd_practice, mtd_practice_ly),
            "last_month_sessions": last_month_total,
            "last_month_sessions_yoy_pct": _yoy_pct(last_month_total, last_month_total_ly),
        },
        "daily_sessions": [{"date": d, **counts} for d, counts in sorted(daily_series.items())],
    }
