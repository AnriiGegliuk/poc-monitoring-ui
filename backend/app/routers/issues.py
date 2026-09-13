from fastapi import APIRouter, Query

from app.data.issues import list_issues
from app.dates import default_date_range

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("")
def get_issues(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    type: list[str] | None = Query(default=None),
    severity: list[str] | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    date_from, date_to = default_date_range(date_from, date_to)
    return list_issues(date_from, date_to, type, severity, search, page, page_size)
