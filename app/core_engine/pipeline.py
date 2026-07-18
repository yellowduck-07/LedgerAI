"""End-to-end orchestration from normalized inputs to Virtual CA outputs.

Expects invoice and transaction dicts matching app/schemas/ contracts. Routers
and OCR parsers should validate upstream, then call run_pipeline().
"""

from __future__ import annotations

from pathlib import Path

from app.core_engine.categorize import categorize_transaction
from app.core_engine.compliance_calendar import get_compliance_snapshot
from app.core_engine.compliance_flags import collect_all_actions, summarize_actions
from app.core_engine.gst import DEFAULT_BUSINESS_STATE, compute_period_summary
from app.core_engine.match import find_best_match
from app.core_engine.tds import compute_tds_summary


def run_pipeline(
    invoices: list[dict],
    transactions: list[dict],
    *,
    business_state: str = DEFAULT_BUSINESS_STATE,
    period: str | None = None,
    as_of: str | None = None,
) -> dict:
    """Run categorize → match → GST → TDS → compliance for one reporting period."""
    categorized = categorize_transactions(transactions)
    payments = categorized

    matches = [
        {
            "invoice": invoice,
            **find_best_match(invoice, categorized),
        }
        for invoice in invoices
        if not invoice.get("is_purchase")
    ]

    reference_date = as_of or _default_as_of(invoices, categorized, period)
    gst_summary = compute_period_summary(invoices, business_state, period)
    tds_summary = compute_tds_summary(payments, period)
    actions = collect_all_actions(invoices, payments, categorized)
    action_summary = summarize_actions(actions)
    calendar = get_compliance_snapshot(reference_date)

    return {
        "period": period,
        "as_of": reference_date,
        "business_state": business_state,
        "transactions": categorized,
        "matches": matches,
        "gst": gst_summary,
        "tds": tds_summary,
        "actions": actions,
        "action_summary": action_summary,
        "compliance_calendar": calendar,
    }


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    """Ensure every transaction has a category from categorize.py."""
    categorized: list[dict] = []

    for transaction in transactions:
        if transaction.get("category"):
            categorized.append(dict(transaction))
            continue

        categorized.append(
            {
                **transaction,
                "category": categorize_transaction(
                    transaction["description"],
                    transaction["direction"],
                ),
            }
        )

    return categorized


def _default_as_of(
    invoices: list[dict],
    transactions: list[dict],
    period: str | None,
) -> str:
    if period:
        return f"{period}-28"

    dates = [item["date"] for item in invoices + transactions if item.get("date")]
    if dates:
        return max(dates)

    return "2026-01-01"


def _load_transactions_csv(path: Path) -> list[dict]:
    import csv

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


if __name__ == "__main__":
    import csv
    import json

    fixtures_dir = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
    invoices = json.loads((fixtures_dir / "sample_invoices.json").read_text())
    transactions = _load_transactions_csv(fixtures_dir / "sample_transactions.csv")

    result = run_pipeline(invoices, transactions, period="2026-01", as_of="2026-01-20")

    print("=== Pipeline integration test ===")
    print(f"period:          {result['period']}")
    print(f"transactions:    {len(result['transactions'])} categorized")
    print(f"matches:         {len(result['matches'])} outward invoices")
    print(f"gst:             {result['gst']}")
    print(f"tds:             {result['tds']}")
    print(f"action_summary:  {result['action_summary']}")
    print(f"calendar:        upcoming={result['compliance_calendar']['upcoming_count']}")
    print()
    print("=== Sample actions ===")
    for action in result["actions"][:5]:
        print(action)

    passed = (
        result["gst"]["net_liability"] > 0
        and result["tds"]["tds_deductible"] > 0
        and result["action_summary"]["total"] > 0
        and result["compliance_calendar"]["upcoming_count"] >= 1
    )
    print()
    print(f"pass:            {passed}")
