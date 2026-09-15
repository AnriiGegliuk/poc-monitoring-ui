"""Unified issue feed: normalizes several dbt report models (each with its own
shape) into one flat, filterable, sortable list of {type, severity, ...}.

Real path queries BigQuery directly against `dbt_reports`:
  - rpt_user_score_drift      -> type "score_drift"
  - rpt_system_loops_weekly   -> type "system_loop"
  - rpt_system_self_answers   -> type "self_answer" (no severity of its own -> LOW)
  - rpt_practice_vs_evaluation -> type "dialog_quality" (derived, see quality_rules)

Add a new issue source by writing one `_fetch_x` function that returns the
normalized shape and appending it in `fetch_real_issues`.
"""

from app.bq import run_query
from app.cache import ttl_cache
from app.config import get_settings
from app.data.mock_store import get_store
from app.data.quality_rules import classify_dialog_quality

SEVERITY_RANK = {"CRITICAL": 4, "WARNING": 3, "MODERATE": 2, "LOW": 1, "INFO": 0}


def list_issues(
    date_from: str,
    date_to: str,
    types: list[str] | None,
    severities: list[str] | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    settings = get_settings()
    all_issues = get_store().issues if settings.use_mock_data else fetch_real_issues(date_from, date_to)

    needle = (search or "").strip().lower()
    filtered = [
        i
        for i in all_issues
        if date_from <= i["occurred_at"][:10] <= date_to
        and (not types or i["type"] in types)
        and (not severities or i["severity"] in severities)
        and (not needle or needle in i["dialog_id"].lower() or needle in (i.get("uid") or "").lower())
    ]
    filtered.sort(key=lambda i: (SEVERITY_RANK.get(i["severity"], 0), i["occurred_at"]), reverse=True)

    counts_by_severity: dict[str, int] = {}
    counts_by_type: dict[str, int] = {}
    for i in filtered:
        counts_by_severity[i["severity"]] = counts_by_severity.get(i["severity"], 0) + 1
        counts_by_type[i["type"]] = counts_by_type.get(i["type"], 0) + 1

    total = len(filtered)
    start = (page - 1) * page_size
    return {
        "items": filtered[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts_by_severity": counts_by_severity,
        "counts_by_type": counts_by_type,
    }


@ttl_cache
def fetch_real_issues(date_from: str, date_to: str) -> list[dict]:
    settings = get_settings()
    return (
        _fetch_score_drift(settings, date_from, date_to)
        + _fetch_system_loops(settings, date_from, date_to)
        + _fetch_self_answers(settings, date_from, date_to)
        + _fetch_dialog_quality(settings, date_from, date_to)
    )


def _fetch_score_drift(settings, date_from: str, date_to: str) -> list[dict]:
    sql = f"""
        SELECT uid, dialog_id, prev_dialog_id, prev_overall_label, current_overall_label,
               drift, drift_severity, drift_direction, scenario_id,
               CAST(dialog_started_at_jst AS STRING) AS occurred_at
        FROM `{settings.reports_ref}.rpt_user_score_drift`
        WHERE drift_severity IN ('WARNING', 'CRITICAL')
          AND DATE(dialog_started_at_jst) BETWEEN @date_from AND @date_to
    """
    rows = run_query(sql, {"date_from": date_from, "date_to": date_to})
    issues = []
    for r in rows:
        direction = (r.get("drift_direction") or "").lower()
        issues.append(
            {
                "id": f"drift-{r['dialog_id']}",
                "type": "score_drift",
                "severity": r["drift_severity"],
                "occurred_at": r["occurred_at"],
                "dialog_id": r["dialog_id"],
                "uid": r.get("uid"),
                "scenario_id": r.get("scenario_id"),
                "title": f"CEFR {direction} {abs(r['drift'])} level(s): "
                f"{r['prev_overall_label']} → {r['current_overall_label']}",
                "description": f"User {r.get('uid')} moved from {r['prev_overall_label']} "
                f"in {r['prev_dialog_id']} to {r['current_overall_label']} in {r['dialog_id']}.",
                "details": r,
            }
        )
    return issues


def _fetch_system_loops(settings, date_from: str, date_to: str) -> list[dict]:
    sql = f"""
        SELECT dialog_id, scenario_id, looped_topic, repeated_phrase, repetition_count,
               severity, llm_model,
               CAST(dialog_started_time_jst AS STRING) AS occurred_at
        FROM `{settings.reports_ref}.rpt_system_loops_weekly`
        WHERE DATE(dialog_started_time_jst) BETWEEN @date_from AND @date_to
    """
    rows = run_query(sql, {"date_from": date_from, "date_to": date_to})
    issues = []
    for r in rows:
        issues.append(
            {
                "id": f"loop-{r['dialog_id']}-{r.get('looped_topic')}-{r.get('repetition_count')}",
                "type": "system_loop",
                "severity": r["severity"],
                "occurred_at": r["occurred_at"],
                "dialog_id": r["dialog_id"],
                "uid": None,
                "scenario_id": r.get("scenario_id"),
                "title": f"System repeated a phrase {r['repetition_count']}x in {r.get('looped_topic')}",
                "description": f'"{r.get("repeated_phrase")}" was repeated {r["repetition_count"]} times.',
                "details": r,
            }
        )
    return issues


def _fetch_self_answers(settings, date_from: str, date_to: str) -> list[dict]:
    sql = f"""
        SELECT dialog_id, self_answer_topic, system_question_sentence, detected_system_self_answer_sentence,
               CAST(dialog_started_at_jst AS STRING) AS occurred_at
        FROM `{settings.reports_ref}.rpt_system_self_answers`
        WHERE dialog_date_jst BETWEEN @date_from AND @date_to
    """
    rows = run_query(sql, {"date_from": date_from, "date_to": date_to})
    issues = []
    for r in rows:
        issues.append(
            {
                "id": f"selfans-{r['dialog_id']}-{r.get('self_answer_topic')}",
                "type": "self_answer",
                "severity": "LOW",
                "occurred_at": r["occurred_at"],
                "dialog_id": r["dialog_id"],
                "uid": None,
                "scenario_id": None,
                "title": f"System asked and answered its own question in {r.get('self_answer_topic')}",
                "description": "The system's turn contained both a question and an immediate answer to it.",
                "details": r,
            }
        )
    return issues


def _fetch_dialog_quality(settings, date_from: str, date_to: str) -> list[dict]:
    sql = f"""
        SELECT dialog_id, uid, scenario_id, CAST(dialog_started_at_jst AS STRING) AS occurred_at,
               poor_network_count, strong_noisy_audio_count, system_echo_count,
               long_pause_over_20s, system_repeated_questions,
               no_opportunity_to_answer, ignored_help_requests
        FROM `{settings.reports_ref}.rpt_practice_vs_evaluation`
        WHERE DATE(dialog_started_at_jst) BETWEEN @date_from AND @date_to
          AND (poor_network_count > 0 OR strong_noisy_audio_count > 0 OR system_echo_count > 0
               OR long_pause_over_20s > 0 OR system_repeated_questions > 0
               OR no_opportunity_to_answer > 0 OR ignored_help_requests > 0)
    """
    rows = run_query(sql, {"date_from": date_from, "date_to": date_to})
    issues = []
    for r in rows:
        classified = classify_dialog_quality(r)
        if not classified:
            continue
        severity, reasons = classified
        issues.append(
            {
                "id": f"quality-{r['dialog_id']}",
                "type": "dialog_quality",
                "severity": severity,
                "occurred_at": r["occurred_at"],
                "dialog_id": r["dialog_id"],
                "uid": r.get("uid"),
                "scenario_id": r.get("scenario_id"),
                "title": f"Dialog quality flag: {reasons[0]}",
                "description": "This dialog " + "; ".join(reasons) + ".",
                "details": {"reasons": reasons},
            }
        )
    return issues
