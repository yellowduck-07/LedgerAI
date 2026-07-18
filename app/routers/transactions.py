from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.extraction.csv_parser import parse_transactions_csv
from app.models import Transaction
from app.services.data_loader import _transaction_to_dict

router = APIRouter()


@router.get("")
def list_transactions(
    period: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    rows = db.query(Transaction).order_by(Transaction.date.desc()).all()
    transactions = [_transaction_to_dict(row) for row in rows]
    if period:
        transactions = [item for item in transactions if item["date"].startswith(period)]
    return {"transactions": transactions, "count": len(transactions)}


@router.post("/upload")
async def upload_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV bank statement.")

    try:
        parsed = parse_transactions_csv(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc

    saved = []
    for item in parsed:
        db.add(
            Transaction(
                date=item["date"],
                description=item["description"],
                amount=item["amount"],
                direction=item["direction"],
                vendor_name=item.get("vendor_name"),
                pan_available=item.get("pan_available", False),
            )
        )
        saved.append(item)

    db.commit()
    return {"saved": len(saved), "transactions": saved}
