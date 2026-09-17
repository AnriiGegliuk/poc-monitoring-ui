"""Turns per-dialog DQA counters into a single 'dialog quality' issue.

These thresholds classify anomalies that are already computed per-dialog in
`fct_dialogs` / `rpt_practice_vs_evaluation` (poor network, ignored help
requests, dead air, ...) but today only exist as columns in a wide table. This
is what turns them into an entry in the Issues feed, applied identically
whether the row came from BigQuery or the mock generator.

Tune the numbers here as you learn what's actually noise vs. signal.
"""


def classify_dialog_quality(row: dict) -> tuple[str, list[str]] | None:
    reasons_critical: list[str] = []
    reasons_warning: list[str] = []
    reasons_moderate: list[str] = []

    if (row.get("no_opportunity_to_answer") or 0) > 0:
        reasons_critical.append(
            f"gave the user no opportunity to answer {row['no_opportunity_to_answer']} time(s)"
        )
    if (row.get("ignored_help_requests") or 0) > 0:
        reasons_critical.append(f"ignored {row['ignored_help_requests']} help request(s)")

    if (row.get("poor_network_count") or 0) > 5:
        reasons_warning.append(f"poor network on {row['poor_network_count']} turns")
    if (row.get("strong_noisy_audio_count") or 0) > 5:
        reasons_warning.append(f"strong background noise on {row['strong_noisy_audio_count']} turns")
    if (row.get("system_echo_count") or 0) > 3:
        reasons_warning.append(f"system echo detected {row['system_echo_count']} times")

    if 0 < (row.get("poor_network_count") or 0) <= 5:
        reasons_moderate.append(f"poor network on {row['poor_network_count']} turn(s)")
    if (row.get("long_pause_over_20s") or 0) > 2:
        reasons_moderate.append(f"{row['long_pause_over_20s']} pause(s) over 20s")
    if (row.get("system_repeated_questions") or 0) > 1:
        reasons_moderate.append(f"repeated the same question {row['system_repeated_questions']} times")

    if reasons_critical:
        return "CRITICAL", reasons_critical
    if reasons_warning:
        return "WARNING", reasons_warning
    if reasons_moderate:
        return "MODERATE", reasons_moderate
    return None
