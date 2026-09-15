"""Dialog explorer: paginated/sortable/filterable table + single-dialog detail.

Real path treats `rpt_practice_vs_evaluation` as the canonical per-dialog row
(it already applies the test-campaign exclusions dbt encodes) and enriches the
detail view with CEFR sub-scores from `rpt_dialogs_with_cefr_and_dqa` plus raw
turns/telemetry from the `dqa_pipeline` dataset.
"""

from app.bq import run_query
from app.cache import ttl_cache
from app.config import get_settings
from app.data.mock_store import generate_telemetry, generate_turns, get_store

SORTABLE_COLUMNS = {
    "dialog_started_at": "dialog_started_at",
    "total_turns": "total_turns",
    "stay_duration": "stay_duration",
    "poor_network_count": "poor_network_count",
    "system_loops_count": "system_loops_count",
    "overall_score": "overall_score",
}

MAX_TURNS_RETURNED = 500


def list_dialogs(
    date_from: str,
    date_to: str,
    dialog_type: str | None,
    cefr_label: str | None,
    scenario_id: str | None,
    search: str | None,
    sort_by: str,
    sort_dir: str,
    page: int,
    page_size: int,
) -> dict:
    settings = get_settings()
    sort_col = SORTABLE_COLUMNS.get(sort_by, "dialog_started_at")
    reverse = sort_dir != "asc"

    if settings.use_mock_data:
        rows = get_store().dialogs
    else:
        rows = fetch_real_dialogs(date_from, date_to)

    needle = (search or "").strip().lower()
    filtered = [
        r
        for r in rows
        if date_from <= r["dialog_started_at"][:10] <= date_to
        and (not dialog_type or r["dialog_type"] == dialog_type)
        and (not cefr_label or r.get("overall_label") == cefr_label)
        and (not scenario_id or r["scenario_id"] == scenario_id)
        and (not needle or needle in r["dialog_id"].lower() or needle in (r.get("uid") or "").lower())
    ]
    filtered.sort(key=lambda r: (r.get(sort_col) is not None, r.get(sort_col)), reverse=reverse)

    total = len(filtered)
    start = (page - 1) * page_size
    return {"items": filtered[start : start + page_size], "total": total, "page": page, "page_size": page_size}


def get_dialog_detail(dialog_id: str) -> dict | None:
    settings = get_settings()

    if settings.use_mock_data:
        row = get_store().dialogs_by_id.get(dialog_id)
        if not row:
            return None
        return {
            "dialog": row,
            "turns": generate_turns(row)[:MAX_TURNS_RETURNED],
            "telemetry": generate_telemetry(row),
        }

    dialog_rows = run_query(
        f"""
        SELECT * FROM `{settings.reports_ref}.rpt_practice_vs_evaluation`
        WHERE dialog_id = @dialog_id LIMIT 1
        """,
        {"dialog_id": dialog_id},
    )
    if not dialog_rows:
        return None
    dialog = dialog_rows[0]

    cefr_rows = run_query(
        f"""
        SELECT fluency_label, fluency_score, accuracy_label, accuracy_score,
               coherence_label, coherence_score, phonology_label, phonology_score,
               interaction_label, interaction_score, range_label, range_score
        FROM `{settings.reports_ref}.rpt_dialogs_with_cefr_and_dqa`
        WHERE dialog_id = @dialog_id LIMIT 1
        """,
        {"dialog_id": dialog_id},
    )
    if cefr_rows:
        dialog.update(cefr_rows[0])

    turns = run_query(
        f"""
        SELECT topic, turn_id, speaker, start_time, end_time, duration_sec, text, word_count,
               gap_between_turns_sec, system_interruption_flag, user_interruption_flag
        FROM `{settings.raw_ref}.fct_turns`
        WHERE dialog_id = @dialog_id
        ORDER BY start_time
        LIMIT {MAX_TURNS_RETURNED}
        """,
        {"dialog_id": dialog_id},
    )

    telemetry_rows = run_query(
        f"SELECT * FROM `{settings.raw_ref}.fct_dialog_telemetry` WHERE dialog_id = @dialog_id LIMIT 1",
        {"dialog_id": dialog_id},
    )

    return {"dialog": dialog, "turns": turns, "telemetry": telemetry_rows[0] if telemetry_rows else None}


@ttl_cache
def fetch_real_dialogs(date_from: str, date_to: str) -> list[dict]:
    settings = get_settings()
    return run_query(
        f"""
        SELECT *
        FROM `{settings.reports_ref}.rpt_practice_vs_evaluation`
        WHERE DATE(dialog_started_at_jst) BETWEEN @date_from AND @date_to
        """,
        {"date_from": date_from, "date_to": date_to},
    )
