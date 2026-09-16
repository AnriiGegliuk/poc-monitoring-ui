"""Deterministic in-memory dataset standing in for BigQuery.

Built once per process, on first access, from a fixed seed - so the app is
fully interactive (`USE_MOCK_DATA=true`, the default) without any GCP
credentials, and every request sees the same data until the process restarts.

Shapes mirror the real report tables closely enough that swapping to
`app/data/*_bq.py` doesn't change what the frontend sees:
  - dialogs      ~ rpt_practice_vs_evaluation + CEFR sub-scores from
                   rpt_dialogs_with_cefr_and_dqa
  - score_drift  ~ rpt_user_score_drift
  - system_loop  ~ rpt_system_loops_weekly
  - self_answer  ~ rpt_system_self_answers
  - dialog_quality: derived the same way real data is, via quality_rules.
"""

import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from app.data.quality_rules import classify_dialog_quality

SCENARIOS = [
    "restaurant-order",
    "job-interview",
    "hotel-checkin",
    "small-talk",
    "doctor-visit",
    "airport-checkin",
]
INTELLA_VERSIONS = ["2.3.0", "2.4.1", "2.5.0", "2.5.2"]
CAMPAIGNS = ["spring-promo", "partner-jp", "organic", "referral-a", None]
CEFR_LEVELS = ["Pre-A1", "A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_WEIGHTS = [2, 10, 22, 28, 22, 12, 4]
CEFR_DIMENSIONS = ["fluency", "accuracy", "coherence", "phonology", "interaction", "range"]

DAYS_OF_HISTORY = 45
N_USERS = 220


def _weighted_choice(rng: random.Random, options: list[str], weights: list[int]) -> str:
    return rng.choices(options, weights=weights, k=1)[0]


def _build_dialogs() -> tuple[list[dict], dict[str, dict]]:
    rng = random.Random(20260831)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    users = [f"u-{i:04d}" for i in range(N_USERS)]

    dialogs: list[dict] = []
    counter = 0

    for day_offset in range(DAYS_OF_HISTORY, -1, -1):
        day = today - timedelta(days=day_offset)
        for _ in range(rng.randint(18, 55)):
            counter += 1
            dialog_id = f"d-{counter:06d}"
            uid = rng.choice(users)
            started_at = day + timedelta(seconds=rng.randint(0, 86399))
            is_canceled = rng.random() < 0.04
            dialog_type = "evaluation" if rng.random() < 0.35 else "practice"

            total_turns = rng.randint(8, 60)
            user_turns = max(1, total_turns // 2 + rng.randint(-3, 3))
            system_turns = max(1, total_turns - user_turns)
            avg_words_per_turn = rng.uniform(4, 14)

            poor_network_count = rng.choices([0, 1, 2, 3, 4, 8], weights=[55, 18, 10, 7, 5, 3])[0]
            noisy_count = rng.choices([0, 1, 2, 3, 6], weights=[65, 15, 10, 6, 3])[0]

            row = {
                "dialog_id": dialog_id,
                "uid": uid,
                "campaign_code": rng.choice(CAMPAIGNS),
                "coupon_code": None,
                "customer_id": f"c-{rng.randint(1000, 9999)}",
                "language": "en",
                "scenario_id": rng.choice(SCENARIOS),
                "scenario_version": rng.randint(1, 4),
                "intella_version": rng.choice(INTELLA_VERSIONS),
                "agent_type": "voice",
                "dialog_type": dialog_type,
                "is_canceled": is_canceled,
                "dialog_started_at": started_at.isoformat(),
                "dialog_started_at_jst": (started_at + timedelta(hours=9)).isoformat(),
                "stay_duration": rng.randint(90, 900),
                "setup_duration": rng.randint(3, 40),
                "cancel_duration_seconds": rng.randint(10, 300) if is_canceled else None,
                "total_turns": total_turns,
                "user_turns": user_turns,
                "system_turns": system_turns,
                "total_words": int(total_turns * avg_words_per_turn),
                "user_words": int(user_turns * avg_words_per_turn * 0.9),
                "system_words": int(system_turns * avg_words_per_turn * 1.1),
                "topic_count": rng.randint(1, 6),
                "user_speaking_time_seconds": rng.randint(30, 400),
                "system_speaking_time_seconds": rng.randint(30, 400),
                "poor_network": poor_network_count > 0,
                "poor_network_count": poor_network_count,
                "has_strong_noisy_audio": noisy_count > 0,
                "strong_noisy_audio_count": noisy_count,
                "avg_snr_db": round(rng.uniform(8, 30), 1),
                "max_snr_db": round(rng.uniform(20, 40), 1),
                "median_network_delay_ms": rng.randint(40, 300),
                "p95_network_delay_ms": rng.randint(200, 900),
                "max_network_delay_ms": rng.randint(400, 2000),
                "long_pause_over_5s": rng.choices([0, 1, 2, 3], weights=[60, 20, 12, 8])[0],
                "long_pause_over_10s": rng.choices([0, 1, 2], weights=[75, 18, 7])[0],
                "long_pause_over_20s": rng.choices([0, 1, 2, 3], weights=[85, 9, 4, 2])[0],
                "system_interruptions": rng.choices([0, 1, 2], weights=[70, 20, 10])[0],
                "user_interruptions": rng.choices([0, 1, 2], weights=[75, 18, 7])[0],
                "avg_system_latency_seconds": round(rng.uniform(0.4, 2.2), 2),
                "max_system_latency_seconds": round(rng.uniform(1.5, 6.0), 2),
                "system_repetition_score": round(rng.uniform(0, 0.3), 3),
                "topics_with_no_user_speech": rng.choices([0, 1], weights=[90, 10])[0],
                "topics_with_only_empty_user_speech": 0,
                "system_repeated_questions": rng.choices([0, 1, 2, 3], weights=[80, 12, 5, 3])[0],
                "no_opportunity_to_answer": rng.choices([0, 1, 2], weights=[93, 5, 2])[0],
                "system_monologue_p95_turns": rng.randint(1, 4),
                "system_echo_count": rng.choices([0, 1, 2, 3, 5], weights=[80, 10, 5, 3, 2])[0],
                "user_help_requests": rng.choices([0, 1, 2], weights=[70, 20, 10])[0],
                "repeated_help_requests": rng.choices([0, 1], weights=[92, 8])[0],
                "ignored_help_requests": rng.choices([0, 1], weights=[96, 4])[0],
                "system_loops_count": 0,
                "topics_with_system_loops": 0,
                "overall_label": None,
                "overall_score": None,
                "has_feedback": rng.random() < 0.3,
            }
            row["feedback_positive"] = (rng.random() < 0.78) if row["has_feedback"] else None

            if dialog_type == "evaluation" and not is_canceled:
                idx = CEFR_LEVELS.index(_weighted_choice(rng, CEFR_LEVELS, CEFR_WEIGHTS))
                row["overall_label"] = CEFR_LEVELS[idx]
                row["overall_score"] = round(idx + rng.uniform(0, 0.9), 2)
                for dim in CEFR_DIMENSIONS:
                    d_idx = max(0, min(6, idx + rng.randint(-1, 1)))
                    row[f"{dim}_label"] = CEFR_LEVELS[d_idx]
                    row[f"{dim}_score"] = round(d_idx + rng.uniform(0, 0.9), 2)

            dialogs.append(row)

    dialogs_by_id = {d["dialog_id"]: d for d in dialogs}
    return dialogs, dialogs_by_id


def _derive_score_drift(dialogs_by_id: dict[str, dict]) -> list[dict]:
    level_idx = {label: i for i, label in enumerate(CEFR_LEVELS)}
    by_user: dict[str, list[dict]] = {}
    for row in dialogs_by_id.values():
        if row["overall_label"]:
            by_user.setdefault(row["uid"], []).append(row)

    issues = []
    for uid, rows in by_user.items():
        ordered = sorted(rows, key=lambda r: r["dialog_started_at"])
        for prev, cur in zip(ordered, ordered[1:]):
            drift = level_idx[cur["overall_label"]] - level_idx[prev["overall_label"]]
            if drift == 0:
                continue
            severity = "CRITICAL" if abs(drift) >= 2 else "WARNING"
            direction = "IMPROVED" if drift > 0 else "DECLINED"
            issues.append(
                {
                    "id": f"drift-{cur['dialog_id']}",
                    "type": "score_drift",
                    "severity": severity,
                    "occurred_at": cur["dialog_started_at"],
                    "dialog_id": cur["dialog_id"],
                    "uid": uid,
                    "scenario_id": cur["scenario_id"],
                    "title": f"CEFR {direction.lower()} {abs(drift)} level(s): "
                    f"{prev['overall_label']} → {cur['overall_label']}",
                    "description": f"User {uid} moved from {prev['overall_label']} in {prev['dialog_id']} "
                    f"to {cur['overall_label']} in {cur['dialog_id']}.",
                    "details": {
                        "prev_dialog_id": prev["dialog_id"],
                        "prev_overall_label": prev["overall_label"],
                        "current_overall_label": cur["overall_label"],
                        "drift": drift,
                        "drift_direction": direction,
                    },
                }
            )
    return issues


PHRASES = [
    "Could you repeat that, please?",
    "Let's move on to the next topic.",
    "That's a great point.",
    "Can you tell me more about that?",
    "I'm sorry, I didn't catch that.",
]


def _derive_system_loops(dialogs: list[dict], rng: random.Random) -> list[dict]:
    issues = []
    for row in dialogs:
        if rng.random() >= 0.06:
            continue
        repetition_count = rng.choices([4, 5, 7, 10, 14], weights=[35, 25, 20, 12, 8])[0]
        severity = "CRITICAL" if repetition_count >= 10 else "MODERATE" if repetition_count >= 5 else "LOW"
        topic = f"topic-{rng.randint(1, row['topic_count'])}"
        issues.append(
            {
                "id": f"loop-{row['dialog_id']}",
                "type": "system_loop",
                "severity": severity,
                "occurred_at": row["dialog_started_at"],
                "dialog_id": row["dialog_id"],
                "uid": row["uid"],
                "scenario_id": row["scenario_id"],
                "title": f"System repeated a phrase {repetition_count}x in {topic}",
                "description": f'"{rng.choice(PHRASES)}" was repeated {repetition_count} times.',
                "details": {
                    "looped_topic": topic,
                    "repeated_phrase": rng.choice(PHRASES),
                    "repetition_count": repetition_count,
                    "llm_model": "gpt-4o-mini",
                },
            }
        )
    return issues


def _derive_self_answers(dialogs: list[dict], rng: random.Random) -> list[dict]:
    issues = []
    for row in dialogs:
        if rng.random() >= 0.04:
            continue
        topic = f"topic-{rng.randint(1, row['topic_count'])}"
        issues.append(
            {
                "id": f"selfans-{row['dialog_id']}",
                "type": "self_answer",
                "severity": "LOW",
                "occurred_at": row["dialog_started_at"],
                "dialog_id": row["dialog_id"],
                "uid": row["uid"],
                "scenario_id": row["scenario_id"],
                "title": f"System asked and answered its own question in {topic}",
                "description": "The system's turn contained both a question and an immediate answer to it.",
                "details": {
                    "topic": topic,
                    "question_sentence": "What do you usually order here?",
                    "candidate_answer_sentence": "I usually order the grilled salmon.",
                },
            }
        )
    return issues


def _derive_dialog_quality(dialogs: list[dict]) -> list[dict]:
    issues = []
    for row in dialogs:
        classified = classify_dialog_quality(row)
        if not classified:
            continue
        severity, reasons = classified
        issues.append(
            {
                "id": f"quality-{row['dialog_id']}",
                "type": "dialog_quality",
                "severity": severity,
                "occurred_at": row["dialog_started_at"],
                "dialog_id": row["dialog_id"],
                "uid": row["uid"],
                "scenario_id": row["scenario_id"],
                "title": f"Dialog quality flag: {reasons[0]}",
                "description": "This dialog " + "; ".join(reasons) + ".",
                "details": {"reasons": reasons},
            }
        )
    return issues


def generate_turns(row: dict) -> list[dict]:
    """Deterministic per-dialog turn list, generated on demand (not stored for
    all ~1800 mock dialogs up front)."""
    rng = random.Random(f"turns-{row['dialog_id']}")
    turns = []
    t = 0.0
    for i in range(row["total_turns"]):
        speaker = "user" if i % 2 == 0 else "system"
        duration = round(rng.uniform(1.5, 12.0), 1)
        word_count = max(1, int(duration * rng.uniform(1.5, 3.0)))
        turns.append(
            {
                "turn_id": i + 1,
                "topic": f"topic-{1 + i // max(1, row['total_turns'] // max(1, row['topic_count']))}",
                "speaker": speaker,
                "start_time": round(t, 1),
                "end_time": round(t + duration, 1),
                "duration_sec": duration,
                "text": f"[{speaker} turn {i + 1} - {word_count} words]",
                "word_count": word_count,
                "gap_between_turns_sec": round(rng.uniform(0.1, 1.5), 2),
                "system_interruption_flag": speaker == "system" and rng.random() < 0.05,
                "user_interruption_flag": speaker == "user" and rng.random() < 0.05,
            }
        )
        t += duration + rng.uniform(0.2, 1.2)
    return turns


TELEMETRY_STAGES = [
    ("asr", 0.15, 0.45),
    ("llm", 0.4, 1.6),
    ("actionplay", 0.05, 0.3),
    ("actiongeneration", 0.1, 0.5),
    ("motionselection", 0.05, 0.2),
    ("audiogeneration", 0.2, 0.8),
]


def generate_telemetry(row: dict) -> dict:
    rng = random.Random(f"telemetry-{row['dialog_id']}")
    out = {"dialog_id": row["dialog_id"], "intella_version": row["intella_version"], "scenario_id": row["scenario_id"]}
    for stage, lo, hi in TELEMETRY_STAGES:
        avg = round(rng.uniform(lo, hi), 3)
        out[f"avg_{stage}_latency_sec"] = avg
        out[f"p95_{stage}_latency_sec"] = round(avg * rng.uniform(1.4, 2.2), 3)
        out[f"{stage}_latency_count"] = rng.randint(row["total_turns"] // 2, row["total_turns"])
    hit = rng.randint(row["total_turns"], row["total_turns"] * 3)
    miss = rng.randint(0, row["total_turns"])
    out["tts_cache_hit_count"] = hit
    out["tts_cache_miss_count"] = miss
    out["tts_cache_hit_rate"] = round(hit / max(1, hit + miss), 3)
    out["avg_tts_total_latency_ms"] = round(rng.uniform(80, 400), 1)
    out["p95_tts_total_latency_ms"] = round(out["avg_tts_total_latency_ms"] * rng.uniform(1.5, 2.5), 1)
    return out


def _build_business_daily(dialogs: list[dict]) -> list[dict]:
    """Mirrors v_dialogs_business_daily_dashboard's shape, derived from the
    same mock dialogs so the two widgets never disagree with each other."""
    rng = random.Random(7)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for d in dialogs:
        day = d["dialog_started_at"][:10]
        group = "test" if rng.random() < 0.03 else ("assessment" if d["dialog_type"] == "evaluation" else "practice")
        counts[(day, group)] += 1
    return [{"started_date": day, "dashboard_group": group, "dialogs": n} for (day, group), n in counts.items()]


class _MockStore:
    def __init__(self):
        self.dialogs, self.dialogs_by_id = _build_dialogs()
        rng = random.Random(1)
        self.issues = (
            _derive_score_drift(self.dialogs_by_id)
            + _derive_system_loops(self.dialogs, rng)
            + _derive_self_answers(self.dialogs, rng)
            + _derive_dialog_quality(self.dialogs)
        )
        self.issues.sort(key=lambda i: i["occurred_at"], reverse=True)
        self.business_daily = _build_business_daily(self.dialogs)


@lru_cache
def get_store() -> _MockStore:
    return _MockStore()
