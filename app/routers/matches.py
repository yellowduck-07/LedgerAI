from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction
from app.services.data_loader import get_data_status
from app.services.pipeline_service import get_pipeline_result

router = APIRouter()


class MatchConfirmRequest(BaseModel):
    invoice_number: str
    transaction_date: str
    transaction_description: str


@router.get("")
def list_matches(period: str | None = Query(default=None), db: Session = Depends(get_db)):
    status = get_data_status(db)
    if not status["analytics_ready"]:
        return {
            "ready": False,
            "matches": [],
            "message": "Upload invoices and bank CSV to reconcile payments.",
        }

    result = get_pipeline_result(db, period)
    return {
        "ready": True,
        "period": result["period"] or period,
        "matches": result["matches"],
    }


@router.post("/confirm")
def confirm_match(request: MatchConfirmRequest, db: Session = Depends(get_db)):
    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.date == request.transaction_date,
            Transaction.description == request.transaction_description,
        )
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    transaction.matched_invoice_number = request.invoice_number
    db.commit()
    return {"status": "confirmed", "invoice_number": request.invoice_number}
