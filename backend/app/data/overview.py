"""Dashboard summary: KPI tiles + time series, built from the same dialog and
issue data as the other pages (no separate source of truth)."""

from collections import Counter, defaultdict

from app.config import get_settings
from app.data.business import get_business_overview
from app.data.dialogs import fetch_real_dialogs
from app.data.issues import SEVERITY_RANK, fetch_real_issues
from app.data.mock_store import get_store

CEFR_ORDER = ["Pre-A1", "A1", "A2", "B1", "B2", "C1", "C2"]


def get_overview(date_from: str, date_to: str) -> dict:
    settings = get_settings()
    if settings.use_mock_data:
        dialogs = get_store().dialogs
        issues = get_store().issues
    else:
        dialogs = fetch_real_dialogs(date_from, date_to)
        issues = fetch_real_issues(date_from, date_to)

    in_range = [d for d in dialogs if date_from <= d["dialog_started_at"][:10] <= date_to]
    in_range_issues = [i for i in issues if date_from <= i["occurred_at"][:10] <= date_to]

    return {
        "business": get_business_overview(date_from, date_to),
        "kpis": _kpis(in_range, in_range_issues),
        "daily_volume": _daily_volume(in_range),
        "daily_poor_network_rate": _daily_rate(in_range, lambda d: bool(d.get("poor_network"))),
        "daily_issue_counts": _daily_issue_counts(in_range_issues),
        "cefr_distribution": _cefr_distribution(in_range),
        "scenario_breakdown": _scenario_breakdown(in_range),
    }


def _kpis(dialogs: list[dict], issues: list[dict]) -> dict:
    total = len(dialogs)
    users = {d["uid"] for d in dialogs if d.get("uid")}
    canceled = sum(1 for d in dialogs if d.get("is_canceled"))
    evaluations = sum(1 for d in dialogs if d.get("dialog_type") == "evaluation")
    poor_network = sum(1 for d in dialogs if d.get("poor_network"))
    stay_durations = [d["stay_duration"] for d in dialogs if d.get("stay_duration") is not None]
    feedback_rows = [d for d in dialogs if d.get("has_feedback")]
    feedback_positive = sum(1 for d in feedback_rows if d.get("feedback_positive"))

    severity_counts = Counter(i["severity"] for i in issues)

    return {
        "total_dialogs": total,
        "distinct_users": len(users),
        "canceled_rate": round(canceled / total, 3) if total else 0,
        "evaluation_share": round(evaluations / total, 3) if total else 0,
        "poor_network_rate": round(poor_network / total, 3) if total else 0,
        "avg_stay_duration_sec": round(sum(stay_durations) / len(stay_durations), 1) if stay_durations else None,
        "feedback_response_count": len(feedback_rows),
        "feedback_positive_rate": round(feedback_positive / len(feedback_rows), 3) if feedback_rows else None,
        "total_issues": len(issues),
        "critical_issues": severity_counts.get("CRITICAL", 0),
        "warning_issues": severity_counts.get("WARNING", 0),
    }


def _daily_volume(dialogs: list[dict]) -> list[dict]:
    by_day: dict[str, Counter] = defaultdict(Counter)
    for d in dialogs:
        day = d["dialog_started_at"][:10]
        by_day[day]["total"] += 1
        by_day[day][d.get("dialog_type", "practice")] += 1
    return [
        {"date": day, "total": c["total"], "practice": c.get("practice", 0), "evaluation": c.get("evaluation", 0)}
        for day, c in sorted(by_day.items())
    ]


def _daily_rate(dialogs: list[dict], predicate) -> list[dict]:
    totals: dict[str, int] = defaultdict(int)
    hits: dict[str, int] = defaultdict(int)
    for d in dialogs:
        day = d["dialog_started_at"][:10]
        totals[day] += 1
        if predicate(d):
            hits[day] += 1
    return [{"date": day, "rate": round(hits[day] / totals[day], 3)} for day in sorted(totals)]


def _daily_issue_counts(issues: list[dict]) -> list[dict]:
    by_day: dict[str, Counter] = defaultdict(Counter)
    for i in issues:
        by_day[i["occurred_at"][:10]][i["severity"]] += 1
    severities = sorted(SEVERITY_RANK, key=lambda s: -SEVERITY_RANK[s])
    return [{"date": day, **{s: c.get(s, 0) for s in severities}} for day, c in sorted(by_day.items())]


def _cefr_distribution(dialogs: list[dict]) -> list[dict]:
    counts = Counter(d["overall_label"] for d in dialogs if d.get("overall_label"))
    return [{"label": label, "count": counts.get(label, 0)} for label in CEFR_ORDER]


def _scenario_breakdown(dialogs: list[dict]) -> list[dict]:
    counts = Counter(d["scenario_id"] for d in dialogs if d.get("scenario_id"))
    return [{"scenario_id": k, "count": v} for k, v in counts.most_common(8)]
