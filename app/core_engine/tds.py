"""Rule-based TDS computation for Indian SMEs.

Payment dict schema (align with categorize.py output + teammate upload later):

    {
        "description": str,
        "amount": float,
        "date": "YYYY-MM-DD",
        "direction": str,           # "debit" | "credit"
        "category": str,            # from categorize.py
        "vendor_name": str | None,
        "pan_available": bool,
    }
"""

from __future__ import annotations

NO_PAN_RATE = 20.0

TDS_DEPOSIT_KEYWORDS = frozenset(
    {
        "tds",
        "challan",
        "income tax",
        "tax deposited",
        "itns",
    }
)

# section → rate (with PAN), threshold per payment, matching categories/keywords
TDS_SECTIONS: dict[str, dict] = {
    "194I": {
        "description": "Rent",
        "rate_with_pan": 10.0,
        # Statutory rule is annual aggregate; simplified per-payment threshold for demo.
        "threshold": 40000.0,
        "categories": {"Rent & Utilities"},
        "keywords": ("rent", "lease", "landlord"),
    },
    "194C": {
        "description": "Contractors",
        "rate_with_pan": 2.0,
        "threshold": 30000.0,
        "categories": set(),
        "keywords": ("contractor", "contract", "labour", "labor", "civil work"),
    },
    "194J": {
        "description": "Professional fees",
        "rate_with_pan": 10.0,
        "threshold": 30000.0,
        "categories": {"Software & Tools", "Taxes & Compliance"},
        "keywords": ("professional", "consulting", "consultant", "legal fees", "ca fees"),
    },
}


def detect_tds_section(payment: dict) -> str | None:
    """Map a debit payment to a TDS section, if applicable."""
    if payment.get("direction", "").casefold() != "debit":
        return None

    amount = float(payment["amount"])
    category = payment.get("category", "")
    searchable = " ".join(
        [
            payment.get("description", ""),
            payment.get("vendor_name") or "",
            category,
        ]
    ).casefold()

    for section, rules in TDS_SECTIONS.items():
        if category in rules["categories"]:
            if amount >= rules["threshold"]:
                return section
            continue

        if any(keyword in searchable for keyword in rules["keywords"]):
            if amount >= rules["threshold"]:
                return section

    return None


def calculate_tds(payment: dict, section: str | None = None) -> dict:
    """Calculate TDS amount for a payment under a given section."""
    resolved_section = section or detect_tds_section(payment)
    if resolved_section is None:
        return {
            "section": None,
            "rate": 0.0,
            "tds_amount": 0.0,
            "applicable": False,
        }

    rules = TDS_SECTIONS[resolved_section]
    amount = float(payment["amount"])
    if amount < rules["threshold"]:
        return {
            "section": resolved_section,
            "rate": 0.0,
            "tds_amount": 0.0,
            "applicable": False,
        }

    rate = rules["rate_with_pan"]
    if not payment.get("pan_available", False):
        rate = NO_PAN_RATE

    tds_amount = round(amount * rate / 100, 2)
    return {
        "section": resolved_section,
        "rate": rate,
        "tds_amount": tds_amount,
        "applicable": True,
    }


def compute_tds_summary(payments: list[dict], period: str | None = None) -> dict:
    """Aggregate deductible TDS, detected deposits, and the gap for a month."""
    filtered = _filter_payments_by_period(payments, period)

    deductible = 0.0
    deposited = 0.0
    by_section: dict[str, float] = {}
    review_count = 0

    for payment in filtered:
        if payment.get("direction", "").casefold() != "debit":
            continue

        if _is_tds_deposit(payment):
            deposited += float(payment["amount"])
            continue

        tds = calculate_tds(payment)
        if tds["applicable"]:
            deductible += tds["tds_amount"]
            section = tds["section"]
            by_section[section] = by_section.get(section, 0.0) + tds["tds_amount"]

        if flag_tds_compliance(payment):
            review_count += 1

    deductible = round(deductible, 2)
    deposited = round(deposited, 2)
    gap = round(max(deductible - deposited, 0.0), 2)

    return {
        "period": period,
        "tds_deductible": deductible,
        "tds_deposited": deposited,
        "pending_deposit": gap,
        "by_section": {section: round(amount, 2) for section, amount in by_section.items()},
        "payments_needing_review": review_count,
    }


def flag_tds_compliance(payment: dict) -> list[dict]:
    """Return rule-based TDS compliance flags for a single payment."""
    flags: list[dict] = []

    if payment.get("direction", "").casefold() != "debit":
        return flags

    section = detect_tds_section(payment)
    if section is None:
        return flags

    if not payment.get("pan_available", False):
        flags.append(
            {
                "type": "missing_pan",
                "severity": "high",
                "message": f"Payment may attract {section} TDS but PAN is unavailable (higher rate applies).",
            }
        )

    tds = calculate_tds(payment, section)
    if tds["applicable"] and not _is_tds_deposit(payment):
        flags.append(
            {
                "type": "tds_required",
                "severity": "medium",
                "message": (
                    f"{section} TDS of ₹{tds['tds_amount']} may be required on this payment."
                ),
            }
        )

    return flags


def _filter_payments_by_period(payments: list[dict], period: str | None) -> list[dict]:
    if period is None:
        return payments

    return [payment for payment in payments if payment["date"].startswith(period)]


def _is_tds_deposit(payment: dict) -> bool:
    description = payment.get("description", "").casefold()
    category = payment.get("category", "").casefold()
    combined = f"{description} {category}"
    return any(keyword in combined for keyword in TDS_DEPOSIT_KEYWORDS)


if __name__ == "__main__":
    test_cases = [
        (
            "Rent payment triggers 194I",
            {
                "description": "Office rent January",
                "amount": 50000.0,
                "date": "2026-01-05",
                "direction": "debit",
                "category": "Rent & Utilities",
                "vendor_name": "Landlord Associates",
                "pan_available": True,
            },
            {"section": "194I", "tds_amount": 5000.0},
        ),
        (
            "Contractor payment above threshold triggers 194C",
            {
                "description": "Civil contractor final bill",
                "amount": 75000.0,
                "date": "2026-01-07",
                "direction": "debit",
                "category": "Uncategorized",
                "vendor_name": "BuildRight Contractors",
                "pan_available": True,
            },
            {"section": "194C", "tds_amount": 1500.0},
        ),
        (
            "Professional fees trigger 194J",
            {
                "description": "CA consulting fees Q4",
                "amount": 40000.0,
                "date": "2026-01-09",
                "direction": "debit",
                "category": "Taxes & Compliance",
                "vendor_name": "Patel & Co",
                "pan_available": True,
            },
            {"section": "194J", "tds_amount": 4000.0},
        ),
        (
            "Below threshold — no TDS",
            {
                "description": "Minor repair contractor",
                "amount": 15000.0,
                "date": "2026-01-11",
                "direction": "debit",
                "category": "Uncategorized",
                "vendor_name": "Quick Fix",
                "pan_available": True,
            },
            {"section": None, "tds_amount": 0.0},
        ),
        (
            "PAN missing — higher rate",
            {
                "description": "Office rent February",
                "amount": 50000.0,
                "date": "2026-01-15",
                "direction": "debit",
                "category": "Rent & Utilities",
                "vendor_name": "Landlord Associates",
                "pan_available": False,
            },
            {"section": "194I", "rate": NO_PAN_RATE, "tds_amount": 10000.0},
        ),
        (
            "TDS deposit detected in bank statement",
            {
                "description": "TDS challan 281 January",
                "amount": 5000.0,
                "date": "2026-01-20",
                "direction": "debit",
                "category": "Taxes & Compliance",
                "vendor_name": "Income Tax Dept",
                "pan_available": True,
            },
            {"is_deposit": True},
        ),
    ]

    for label, payment, expected in test_cases:
        section = detect_tds_section(payment)
        tds = calculate_tds(payment)
        flags = flag_tds_compliance(payment)
        is_deposit = _is_tds_deposit(payment)

        print(f"=== {label} ===")
        print(f"section:  {section}")
        print(f"tds:      {tds}")
        print(f"flags:    {flags}")
        print(f"deposit:  {is_deposit}")

        if expected.get("is_deposit"):
            passed = is_deposit
        else:
            passed = tds["section"] == expected["section"] and tds["tds_amount"] == expected["tds_amount"]
            if "rate" in expected:
                passed = passed and tds["rate"] == expected["rate"]

        print(f"pass:     {passed}")
        print()

    summary_payments = [payment for _, payment, _ in test_cases]
    summary = compute_tds_summary(summary_payments, "2026-01")
    print("=== TDS summary for 2026-01 ===")
    print(summary)
    print(
        "pass:     "
        f"{summary['tds_deductible'] == 20500.0 and summary['tds_deposited'] == 5000.0 and summary['pending_deposit'] == 15500.0}"
    )
