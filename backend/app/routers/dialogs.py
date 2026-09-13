from fastapi import APIRouter, HTTPException, Query

from app.data.dialogs import get_dialog_detail, list_dialogs
from app.dates import default_date_range

router = APIRouter(prefix="/api/dialogs", tags=["dialogs"])


@router.get("")
def get_dialogs(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    dialog_type: str | None = Query(default=None),
    cefr_label: str | None = Query(default=None),
    scenario_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="dialog_started_at"),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    date_from, date_to = default_date_range(date_from, date_to)
    return list_dialogs(
        date_from, date_to, dialog_type, cefr_label, scenario_id, search, sort_by, sort_dir, page, page_size
    )


@router.get("/{dialog_id}")
def get_dialog(dialog_id: str):
    detail = get_dialog_detail(dialog_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"dialog {dialog_id} not found")
    return detail
