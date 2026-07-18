from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.data_loader import get_data_status
from app.services.pipeline_service import get_pipeline_result

router = APIRouter()


@router.get("")
def dashboard(period: str | None = Query(default=None), db: Session = Depends(get_db)):
    status = get_data_status(db)

    if not status["analytics_ready"]:
        return {
            "ready": False,
            "invoice_count": status["invoice_count"],
            "transaction_count": status["transaction_count"],
            "message": _empty_message(status),
            "period": period,
        }

    result = get_pipeline_result(db, period)
    period_invoices = result["gst"]["outward_invoice_count"] + result["gst"]["purchase_invoice_count"]
    period_transactions = len(result["transactions"])

    if period and period_invoices == 0 and period_transactions == 0:
        return {
            "ready": True,
            "has_period_data": False,
            "invoice_count": status["invoice_count"],
            "transaction_count": status["transaction_count"],
            "period": period,
            "message": f"No uploaded records found for {period}. Try another period.",
        }

    return {
        "ready": True,
        "has_period_data": True,
        "period": result["period"] or period,
        "as_of": result["as_of"],
        "invoice_count": status["invoice_count"],
        "transaction_count": status["transaction_count"],
        "gst": result["gst"],
        "tds": result["tds"],
        "action_summary": result["action_summary"],
        "compliance_calendar": _serialize_calendar(result["compliance_calendar"]),
        "match_stats": _match_stats(result["matches"]),
        "category_breakdown": _category_breakdown(result["transactions"]),
    }


def _empty_message(status: dict) -> str:
    missing = []
    if status["invoice_count"] == 0:
        missing.append("invoice PDFs or JSON")
    if status["transaction_count"] == 0:
        missing.append("bank CSV")
    return f"Upload {' and '.join(missing)} to unlock GST, TDS, and reconciliation."


def _match_stats(matches: list[dict]) -> dict:
    auto = sum(1 for match in matches if match.get("status") == "auto")
    review = sum(1 for match in matches if match.get("status") == "review")
    unmatched = sum(1 for match in matches if match.get("transaction") is None)
    return {"auto": auto, "review": review, "unmatched": unmatched, "total": len(matches)}


def _category_breakdown(transactions: list[dict]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for transaction in transactions:
        category = transaction.get("category", "Uncategorized")
        breakdown[category] = breakdown.get(category, 0) + 1
    return breakdown


def _serialize_calendar(calendar: dict) -> dict:
    upcoming = []
    for item in calendar.get("upcoming", []):
        entry = dict(item)
        due_date = entry.get("due_date")
        if hasattr(due_date, "isoformat"):
            entry["due_date"] = due_date.isoformat()
        upcoming.append(entry)

    overdue = []
    for item in calendar.get("overdue", []):
        entry = dict(item)
        due_date = entry.get("due_date")
        if hasattr(due_date, "isoformat"):
            entry["due_date"] = due_date.isoformat()
        overdue.append(entry)

    return {
        "upcoming_count": calendar.get("upcoming_count", 0),
        "overdue_count": calendar.get("overdue_count", 0),
        "upcoming": upcoming,
        "overdue": overdue,
    }
