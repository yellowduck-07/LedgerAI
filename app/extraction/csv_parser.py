"""Parse bank statement CSV uploads into transaction dicts."""

from __future__ import annotations

import csv
import io

from app.schemas.transaction import TransactionSchema


def parse_transactions_csv(content: str | bytes) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    transactions: list[dict] = []

    for row in reader:
        transaction = TransactionSchema.from_engine_dict(
            {
                "date": row["date"].strip(),
                "description": row["description"].strip(),
                "amount": float(row["amount"]),
                "direction": row["direction"].strip(),
                "vendor_name": (row.get("vendor_name") or "").strip() or None,
                "pan_available": (row.get("pan_available") or "").strip().lower()
                == "true",
            }
        )
        transactions.append(transaction.to_engine_dict())

    return transactions
