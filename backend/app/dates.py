from datetime import date, timedelta

DEFAULT_WINDOW_DAYS = 30


def default_date_range(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    """Fill in a trailing-30-day window when the caller doesn't pin dates."""
    today = date.today()
    resolved_to = date_to or today.isoformat()
    resolved_from = date_from or (today - timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
    return resolved_from, resolved_to
