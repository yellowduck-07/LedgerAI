"""Load invoice/transaction data from the database (fixture fallback for tests)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Invoice, Transaction

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def get_data_status(db: Session) -> dict:
    invoice_count = db.query(Invoice).count()
    transaction_count = db.query(Transaction).count()
    return {
        "invoice_count": invoice_count,
        "transaction_count": transaction_count,
        "analytics_ready": invoice_count > 0 and transaction_count > 0,
    }


def load_period_data(
    db: Session | None = None,
    period: str | None = None,
) -> tuple[list[dict], list[dict]]:
    if db is None:
        return _load_fixture_data(period)

    invoices = [_invoice_to_dict(row) for row in db.query(Invoice).all()]
    transactions = [_transaction_to_dict(row) for row in db.query(Transaction).all()]

    if period is None:
        return invoices, transactions

    return (
        [item for item in invoices if item["date"].startswith(period)],
        [item for item in transactions if item["date"].startswith(period)],
    )


def seed_demo_data(db: Session, force: bool = False) -> dict:
    """Load fixture data into the database."""
    if not force and db.query(Invoice).count() > 0:
        return {"seeded": False, "message": "Database already has data."}

    if force:
        db.query(Transaction).delete()
        db.query(Invoice).delete()
        db.commit()

    invoices, transactions = _load_fixture_data(None)
    for invoice in invoices:
        db.add(Invoice(**invoice))
    for transaction in transactions:
        db.add(Transaction(**{**transaction, "category": None}))
    db.commit()
    return {
        "seeded": True,
        "invoices": len(invoices),
        "transactions": len(transactions),
    }


def _load_fixture_data(period: str | None) -> tuple[list[dict], list[dict]]:
    invoices = json.loads((FIXTURES_DIR / "sample_invoices.json").read_text())
    transactions = _load_transactions_csv(FIXTURES_DIR / "sample_transactions.csv")
    if period is None:
        return invoices, transactions
    return (
        [item for item in invoices if item["date"].startswith(period)],
        [item for item in transactions if item["date"].startswith(period)],
    )


def _load_transactions_csv(path: Path) -> list[dict]:
    transactions: list[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            transactions.append(
                {
                    "date": row["date"],
                    "description": row["description"],
                    "amount": float(row["amount"]),
                    "direction": row["direction"],
                    "vendor_name": row.get("vendor_name") or None,
                    "pan_available": row.get("pan_available", "").lower() == "true",
                }
            )
    return transactions


def _invoice_to_dict(row: Invoice) -> dict:
    return {
        "invoice_number": row.invoice_number,
        "date": row.date,
        "amount": row.amount,
        "customer_name": row.customer_name or "",
        "vendor_name": row.vendor_name,
        "is_purchase": row.is_purchase,
        "gstin": row.gstin,
        "gst_rate": row.gst_rate,
        "place_of_supply": row.place_of_supply or "",
        "supply_type": row.supply_type or "B2C",
        "hsn_sac": row.hsn_sac,
    }


def _transaction_to_dict(row: Transaction) -> dict:
    data = {
        "description": row.description,
        "amount": row.amount,
        "date": row.date,
        "direction": row.direction,
        "vendor_name": row.vendor_name,
        "pan_available": row.pan_available,
    }
    if row.category:
        data["category"] = row.category
    return data
