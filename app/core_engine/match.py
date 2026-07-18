from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher

CONFIDENCE_THRESHOLD = 95.0


def find_best_match(invoice: dict, candidate_transactions: list[dict]) -> dict:
    """Return the best-matching transaction for an invoice, if any."""
    invoice_date = datetime.strptime(invoice["date"], "%Y-%m-%d").date()
    candidates = [
        transaction
        for transaction in candidate_transactions
        if abs(
            (
                datetime.strptime(transaction["date"], "%Y-%m-%d").date()
                - invoice_date
            ).days
        )
        <= 10
    ]

    if not candidates:
        return {"transaction": None, "confidence": 0.0, "status": "review"}

    best_transaction = candidates[0]
    best_score = score_match(invoice, best_transaction)

    for transaction in candidates[1:]:
        score = score_match(invoice, transaction)
        if score > best_score:
            best_score = score
            best_transaction = transaction

    status = "auto" if best_score >= CONFIDENCE_THRESHOLD else "review"
    return {
        "transaction": best_transaction,
        "confidence": best_score,
        "status": status,
    }


def score_match(invoice: dict, transaction: dict) -> float:
    """Score how well a transaction matches an invoice (0-100)."""
    amount_score = _score_amount(invoice["amount"], transaction["amount"])
    date_score = _score_date(invoice["date"], transaction["date"])
    name_score = _score_name(invoice["customer_name"], transaction["description"])
    return amount_score + date_score + name_score


def _score_amount(invoice_amount: float, transaction_amount: float) -> float:
    # Weight: 50 — amount is the strongest signal for payment matching.
    if invoice_amount == transaction_amount:
        return 50.0

    if invoice_amount == 0:
        return 0.0

    percent_diff = abs(invoice_amount - transaction_amount) / abs(invoice_amount) * 100

    if percent_diff <= 1:
        return 40.0
    if percent_diff <= 5:
        return 20.0
    return 0.0


def _score_date(invoice_date: str, transaction_date: str) -> float:
    # Weight: 25 — payments usually land near the invoice date.
    invoice_dt = datetime.strptime(invoice_date, "%Y-%m-%d").date()
    transaction_dt = datetime.strptime(transaction_date, "%Y-%m-%d").date()
    day_diff = abs((invoice_dt - transaction_dt).days)

    if day_diff == 0:
        return 25.0
    if day_diff <= 3:
        return 15.0
    if day_diff <= 7:
        return 5.0
    return 0.0


def _score_name(customer_name: str, description: str) -> float:
    # Weight: 25 — name overlap in the bank description helps disambiguate ties.
    normalized_name = customer_name.strip().casefold()
    normalized_description = description.strip().casefold()
    similarity = SequenceMatcher(None, normalized_name, normalized_description).ratio()
    return similarity * 25.0


if __name__ == "__main__":
    invoice = {
        "invoice_number": "INV-1001",
        "customer_name": "Acme Corp",
        "amount": 1000.0,
        "date": "2026-01-15",
    }

    test_cases = [
        (
            "Exact match",
            [
                {"description": "Acme Corp", "amount": 1000.0, "date": "2026-01-15"},
            ],
        ),
        (
            "Close but not exact amount (0.5% off)",
            [
                {"description": "Acme Corp", "amount": 1005.0, "date": "2026-01-15"},
            ],
        ),
        (
            "Date outside 10-day window",
            [
                {"description": "Acme Corp", "amount": 1000.0, "date": "2026-02-01"},
            ],
        ),
        (
            "Completely unrelated transactions",
            [
                {"description": "Netflix Subscription", "amount": 15.99, "date": "2026-01-16"},
                {"description": "Office Supplies Inc", "amount": 250.0, "date": "2026-01-17"},
            ],
        ),
    ]

    for label, candidates in test_cases:
        result = find_best_match(invoice, candidates)
        print(f"=== {label} ===")
        print(result)
        print()
