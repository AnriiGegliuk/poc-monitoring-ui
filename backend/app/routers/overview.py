from fastapi import APIRouter, Query

from app.data.overview import get_overview
from app.dates import default_date_range

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("")
def overview(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    date_from, date_to = default_date_range(date_from, date_to)
    return get_overview(date_from, date_to)
