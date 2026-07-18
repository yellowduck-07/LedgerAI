from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.data_loader import get_data_status
from app.services.pipeline_service import get_pipeline_result

router = APIRouter()


@router.get("")
def list_actions(period: str | None = Query(default=None), db: Session = Depends(get_db)):
    status = get_data_status(db)
    if not status["analytics_ready"]:
        return {
            "ready": False,
            "actions": [],
            "action_summary": {"total": 0, "by_severity": {"high": 0, "medium": 0, "low": 0}, "by_source": {}},
            "message": "Upload invoices and bank CSV to see compliance actions.",
        }

    result = get_pipeline_result(db, period)
    return {
        "ready": True,
        "period": result["period"] or period,
        "actions": result["actions"],
        "action_summary": result["action_summary"],
    }
