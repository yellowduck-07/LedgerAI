from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.extraction.invoice_parser import parse_invoice_upload_detailed
from app.models import Invoice
from app.schemas.invoice import InvoiceSchema
from app.services.data_loader import _invoice_to_dict

router = APIRouter()


@router.get("")
def list_invoices(period: str | None = Query(default=None), db: Session = Depends(get_db)):
    rows = db.query(Invoice).order_by(Invoice.date.desc()).all()
    invoices = [_invoice_to_dict(row) for row in rows]
    if period:
        invoices = [item for item in invoices if item["date"].startswith(period)]
    return {"invoices": invoices, "count": len(invoices)}


@router.post("/upload")
async def upload_invoices(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    filename = file.filename or "upload.bin"

    try:
        parsed = parse_invoice_upload_detailed(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse invoice file: {exc}") from exc

    saved = []
    for item in parsed["invoices"]:
        validated = InvoiceSchema.from_engine_dict(item).to_engine_dict()
        db.add(Invoice(**validated))
        saved.append(validated)

    db.commit()
    return {
        "saved": len(saved),
        "invoices": saved,
        "filename": filename,
        "extraction_method": parsed["extraction_method"],
        "extraction_methods": parsed.get("extraction_methods", []),
        "raw_text_preview": parsed.get("raw_text_preview"),
    }


@router.post("/ocr")
async def ocr_invoice_preview(
    file: UploadFile = File(...),
):
    """Extract invoice fields without saving — useful for OCR review in the UI."""
    content = await file.read()
    filename = file.filename or "upload.bin"

    try:
        parsed = parse_invoice_upload_detailed(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(ex)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OCR failed: {exc}") from exc

    return {
        "filename": filename,
        "extraction_method": parsed["extraction_method"],
        "invoices": parsed["invoices"],
        "raw_text_preview": parsed.get("raw_text_preview"),
    }


@router.post("")
def create_invoice(invoice: InvoiceSchema, db: Session = Depends(get_db)):
    data = invoice.to_engine_dict()
    db.add(Invoice(**data))
    db.commit()
    return {"invoice": data}
