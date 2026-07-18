"""Aggregate compliance actions from GST, TDS, and invoice matching.

Turns scattered rule outputs into a single Action Center feed the dashboard
or `/actions` router can render without duplicating business logic.

Inputs:

    invoices: list[dict]       # gst.py invoice schema
    payments: list[dict]       # tds.py payment schema
    transactions: list[dict]   # optional, for match review flags
"""

from __future__ import annotations

from app.core_engine.gst import flag_gst_compliance
from app.core_engine.match import find_best_match
from app.core_engine.tds import flag_tds_compliance

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def collect_invoice_flags(invoices: list[dict]) -> list[dict]:
    """GST compliance flags for all invoices."""
    actions: list[dict] = []

    for invoice in invoices:
        for flag in flag_gst_compliance(invoice):
            actions.append(
                _wrap_action(
                    flag,
                    source="gst",
                    entity_type="invoice",
                    entity_id=invoice.get("invoice_number"),
                    entity_label=_invoice_label(invoice),
                )
            )

    return actions


def collect_payment_flags(payments: list[dict]) -> list[dict]:
    """TDS compliance flags for all debit payments."""
    actions: list[dict] = []

    for payment in payments:
        for flag in flag_tds_compliance(payment):
            actions.append(
                _wrap_action(
                    flag,
                    source="tds",
                    entity_type="payment",
                    entity_id=payment.get("date"),
                    entity_label=_payment_label(payment),
                )
            )

    return actions


def collect_match_review_flags(
    invoices: list[dict],
    transactions: list[dict],
) -> list[dict]:
    """Flag invoices that did not auto-match to a bank transaction."""
    actions: list[dict] = []

    for invoice in invoices:
        if invoice.get("is_purchase"):
            continue

        result = find_best_match(invoice, transactions)
        if result["status"] != "review":
            continue

        confidence = result["confidence"]
        if result["transaction"] is None:
            message = (
                f"No bank transaction matched invoice {_invoice_label(invoice)} "
                f"within the date window."
            )
            severity = "high"
        else:
            message = (
                f"Invoice {_invoice_label(invoice)} matched with low confidence "
                f"({confidence:.1f}/100) — manual review recommended."
            )
            severity = "medium"

        actions.append(
            {
                "type": "match_review",
                "severity": severity,
                "message": message,
                "source": "match",
                "entity_type": "invoice",
                "entity_id": invoice.get("invoice_number"),
                "entity_label": _invoice_label(invoice),
                "confidence": confidence,
            }
        )

    return actions


def collect_all_actions(
    invoices: list[dict],
    payments: list[dict],
    transactions: list[dict] | None = None,
) -> list[dict]:
    """Merge GST, TDS, and match flags sorted by severity."""
    actions: list[dict] = []
    actions.extend(collect_invoice_flags(invoices))
    actions.extend(collect_payment_flags(payments))

    if transactions is not None:
        actions.extend(collect_match_review_flags(invoices, transactions))

    return sorted(
        actions,
        key=lambda item: (
            SEVERITY_ORDER.get(item["severity"], 99),
            item["source"],
            item.get("entity_id") or "",
        ),
    )


def summarize_actions(actions: list[dict]) -> dict:
    """Counts by severity and source for dashboard badges."""
    by_severity: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    by_source: dict[str, int] = {}

    for action in actions:
        severity = action.get("severity", "low")
        by_severity[severity] = by_severity.get(severity, 0) + 1

        source = action.get("source", "unknown")
        by_source[source] = by_source.get(source, 0) + 1

    return {
        "total": len(actions),
        "by_severity": by_severity,
        "by_source": by_source,
    }


def _wrap_action(
    flag: dict,
    source: str,
    entity_type: str,
    entity_id: str | None,
    entity_label: str,
) -> dict:
    return {
        **flag,
        "source": source,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_label": entity_label,
    }


def _invoice_label(invoice: dict) -> str:
    number = invoice.get("invoice_number") or "unknown"
    party = invoice.get("customer_name") or invoice.get("vendor_name") or "unknown party"
    return f"{number} ({party})"


def _payment_label(payment: dict) -> str:
    description = payment.get("description", "payment")
    amount = payment.get("amount", 0)
    return f"{description} — ₹{amount}"


if __name__ == "__main__":
    invoices = [
        {
            "invoice_number": "P-002",
            "date": "2026-01-09",
            "amount": 1500.0,
            "customer_name": "",
            "vendor_name": "Unknown Supplier",
            "is_purchase": True,
            "gstin": None,
            "gst_rate": 18.0,
            "place_of_supply": "Maharashtra",
            "supply_type": "B2B",
            "hsn_sac": None,
        },
        {
            "invoice_number": "S-001",
            "date": "2026-01-10",
            "amount": 10000.0,
            "customer_name": "Local Retailer",
            "vendor_name": None,
            "is_purchase": False,
            "gstin": "27AABCU9603R1ZM",
            "gst_rate": 18.0,
            "place_of_supply": "Maharashtra",
            "supply_type": "B2B",
            "hsn_sac": "998314",
        },
        {
            "invoice_number": "S-002",
            "date": "2026-01-12",
            "amount": 5000.0,
            "customer_name": "Karnataka Buyer",
            "vendor_name": None,
            "is_purchase": False,
            "gstin": "29AABCU9603R1Z5",
            "gst_rate": 18.0,
            "place_of_supply": "Karnataka",
            "supply_type": "B2B",
            "hsn_sac": "998314",
        },
    ]

    payments = [
        {
            "description": "Office rent January",
            "amount": 50000.0,
            "date": "2026-01-05",
            "direction": "debit",
            "category": "Rent & Utilities",
            "vendor_name": "Landlord Associates",
            "pan_available": False,
        },
        {
            "description": "Civil contractor final bill",
            "amount": 75000.0,
            "date": "2026-01-07",
            "direction": "debit",
            "category": "Uncategorized",
            "vendor_name": "BuildRight Contractors",
            "pan_available": True,
        },
    ]

    transactions = [
        {
            "description": "Local Retailer partial pay",
            "amount": 9000.0,
            "date": "2026-01-11",
        },
    ]

    actions = collect_all_actions(invoices, payments, transactions)
    summary = summarize_actions(actions)

    print("=== All compliance actions ===")
    for action in actions:
        print(action)

    print()
    print("=== Summary ===")
    print(summary)

    gst_count = summary["by_source"].get("gst", 0)
    tds_count = summary["by_source"].get("tds", 0)
    match_count = summary["by_source"].get("match", 0)
    high_count = summary["by_severity"].get("high", 0)

    print()
    print(
        "pass:      "
        f"{gst_count >= 2 and tds_count >= 1 and match_count >= 1 and high_count >= 2}"
    )
