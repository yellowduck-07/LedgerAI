"""Rule-based GST computation for Indian SMEs.

Invoice dict schema (align with teammate OCR output later):

    {
        "invoice_number": str,
        "date": "YYYY-MM-DD",
        "amount": float,              # taxable value BEFORE GST (pre-tax base)
        "customer_name": str,         # counterparty on outward supplies
        "vendor_name": str | None,    # counterparty on inward supplies
        "is_purchase": bool,          # False = outward supply, True = inward / ITC
        "gstin": str | None,          # counterparty GSTIN (15 chars when valid)
        "gst_rate": float,            # 0, 5, 12, 18, or 28
        "place_of_supply": str,       # state name or 2-digit code
        "supply_type": str,           # "B2B" | "B2C"
        "hsn_sac": str | None,
    }

Business context:

    business_state: str  # registered place of business, e.g. "Maharashtra" or "27"
"""

from __future__ import annotations

DEFAULT_BUSINESS_STATE = "Maharashtra"

VALID_GST_RATES = frozenset({0.0, 5.0, 12.0, 18.0, 28.0})

STATE_CODES: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "27": "Maharashtra",
    "29": "Karnataka",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "36": "Telangana",
}


def compute_outward_tax(invoice: dict, business_state: str = DEFAULT_BUSINESS_STATE) -> dict:
    """Compute CGST/SGST or IGST on an outward supply invoice."""
    taxable_value = float(invoice["amount"])
    gst_rate = float(invoice["gst_rate"])
    tax_amount = round(taxable_value * gst_rate / 100, 2)

    if gst_rate == 0:
        return {
            "taxable_value": taxable_value,
            "gst_rate": gst_rate,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": 0.0,
            "total_tax": 0.0,
            "tax_type": "exempt",
        }

    if _is_interstate(invoice["place_of_supply"], business_state):
        return {
            "taxable_value": taxable_value,
            "gst_rate": gst_rate,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": tax_amount,
            "total_tax": tax_amount,
            "tax_type": "IGST",
        }

    half_tax = round(tax_amount / 2, 2)
    return {
        "taxable_value": taxable_value,
        "gst_rate": gst_rate,
        "cgst": half_tax,
        "sgst": half_tax,
        "igst": 0.0,
        "total_tax": tax_amount,
        "tax_type": "CGST+SGST",
    }


def check_itc_eligibility(invoice: dict) -> dict:
    """Determine whether input tax credit can be claimed on a purchase invoice."""
    reasons: list[str] = []

    if not invoice.get("is_purchase"):
        reasons.append("not_a_purchase")
    if float(invoice.get("gst_rate", 0)) <= 0:
        reasons.append("zero_rated_or_exempt")
    if not _is_valid_gstin(invoice.get("gstin")):
        reasons.append("missing_or_invalid_vendor_gstin")
    if invoice.get("supply_type", "").upper() != "B2B":
        reasons.append("not_b2b_supply")

    eligible = len(reasons) == 0
    tax_breakup = compute_outward_tax(invoice)
    itc_amount = tax_breakup["total_tax"] if eligible else 0.0

    return {
        "eligible": eligible,
        "itc_amount": itc_amount,
        "reasons": reasons,
    }


def compute_period_summary(
    invoices: list[dict],
    business_state: str = DEFAULT_BUSINESS_STATE,
    period: str | None = None,
) -> dict:
    """Aggregate output tax, eligible ITC, and net liability for a calendar month."""
    filtered = _filter_invoices_by_period(invoices, period)

    output_tax = 0.0
    eligible_itc = 0.0
    outward_count = 0
    purchase_count = 0

    for invoice in filtered:
        if invoice.get("is_purchase"):
            purchase_count += 1
            itc = check_itc_eligibility(invoice)
            eligible_itc += itc["itc_amount"]
        else:
            outward_count += 1
            tax = compute_outward_tax(invoice, business_state)
            output_tax += tax["total_tax"]

    output_tax = round(output_tax, 2)
    eligible_itc = round(eligible_itc, 2)
    net_liability = round(max(output_tax - eligible_itc, 0.0), 2)

    return {
        "period": period,
        "outward_invoice_count": outward_count,
        "purchase_invoice_count": purchase_count,
        "output_tax": output_tax,
        "eligible_itc": eligible_itc,
        "net_liability": net_liability,
    }


def flag_gst_compliance(invoice: dict) -> list[dict]:
    """Return rule-based compliance flags for a single invoice."""
    flags: list[dict] = []

    if float(invoice.get("gst_rate", 0)) not in VALID_GST_RATES:
        flags.append(
            {
                "type": "invalid_gst_rate",
                "severity": "high",
                "message": f"GST rate {invoice.get('gst_rate')} is not a standard slab.",
            }
        )

    if invoice.get("is_purchase") and invoice.get("supply_type", "").upper() == "B2B":
        if not _is_valid_gstin(invoice.get("gstin")):
            flags.append(
                {
                    "type": "missing_gstin",
                    "severity": "high",
                    "message": "B2B purchase missing valid vendor GSTIN — ITC not claimable.",
                }
            )
        if not invoice.get("hsn_sac"):
            flags.append(
                {
                    "type": "missing_hsn_sac",
                    "severity": "medium",
                    "message": "Purchase invoice missing HSN/SAC code.",
                }
            )

    if not invoice.get("is_purchase") and invoice.get("supply_type", "").upper() == "B2B":
        if not _is_valid_gstin(invoice.get("gstin")):
            flags.append(
                {
                    "type": "missing_customer_gstin",
                    "severity": "medium",
                    "message": "B2B sale missing customer GSTIN.",
                }
            )

    if not invoice.get("place_of_supply"):
        flags.append(
            {
                "type": "missing_place_of_supply",
                "severity": "high",
                "message": "Place of supply is required for correct tax split.",
            }
        )

    return flags


def _filter_invoices_by_period(invoices: list[dict], period: str | None) -> list[dict]:
    if period is None:
        return invoices

    return [invoice for invoice in invoices if invoice["date"].startswith(period)]


def _normalize_state(value: str) -> str:
    cleaned = value.strip().casefold()
    if cleaned.isdigit() and len(cleaned) == 2:
        return cleaned

    for code, name in STATE_CODES.items():
        if cleaned == name.casefold() or cleaned == code:
            return code

    return cleaned


def _is_interstate(place_of_supply: str, business_state: str) -> bool:
    supply_state = _normalize_state(place_of_supply)
    business = _normalize_state(business_state)
    return supply_state != business


def _is_valid_gstin(gstin: str | None) -> bool:
    if not gstin:
        return False
    cleaned = gstin.strip().upper()
    if len(cleaned) != 15:
        return False
    return cleaned[:2].isdigit() and cleaned[2].isalpha() and cleaned[-1].isalnum()


if __name__ == "__main__":
    business_state = DEFAULT_BUSINESS_STATE

    test_cases = [
        (
            "Intrastate B2B sale (CGST+SGST)",
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
            {"tax_type": "CGST+SGST", "total_tax": 1800.0},
        ),
        (
            "Interstate sale (IGST)",
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
            {"tax_type": "IGST", "total_tax": 900.0},
        ),
        (
            "Eligible purchase ITC",
            {
                "invoice_number": "P-001",
                "date": "2026-01-08",
                "amount": 2000.0,
                "customer_name": "",
                "vendor_name": "Cloud Vendor Pvt Ltd",
                "is_purchase": True,
                "gstin": "27AABCU9603R1ZM",
                "gst_rate": 18.0,
                "place_of_supply": "Maharashtra",
                "supply_type": "B2B",
                "hsn_sac": "998313",
            },
            {"eligible": True, "itc_amount": 360.0},
        ),
        (
            "Purchase missing vendor GSTIN",
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
                "hsn_sac": "8471",
            },
            {"eligible": False},
        ),
        (
            "B2C outward supply",
            {
                "invoice_number": "S-003",
                "date": "2026-01-14",
                "amount": 800.0,
                "customer_name": "Walk-in Customer",
                "vendor_name": None,
                "is_purchase": False,
                "gstin": None,
                "gst_rate": 5.0,
                "place_of_supply": "Maharashtra",
                "supply_type": "B2C",
                "hsn_sac": "6109",
            },
            {"tax_type": "CGST+SGST", "total_tax": 40.0},
        ),
    ]

    for label, invoice, expected in test_cases:
        tax = compute_outward_tax(invoice, business_state)
        itc = check_itc_eligibility(invoice)
        flags = flag_gst_compliance(invoice)

        print(f"=== {label} ===")
        print(f"tax:   {tax}")
        print(f"itc:   {itc}")
        print(f"flags: {flags}")

        if "tax_type" in expected:
            passed = tax["tax_type"] == expected["tax_type"] and tax["total_tax"] == expected["total_tax"]
        else:
            passed = itc["eligible"] == expected["eligible"]
            if expected.get("itc_amount") is not None:
                passed = passed and itc["itc_amount"] == expected["itc_amount"]

        print(f"pass:  {passed}")
        print()

    period_invoices = [invoice for _, invoice, _ in test_cases]
    summary = compute_period_summary(period_invoices, business_state, "2026-01")
    print("=== Net liability for 2026-01 ===")
    print(summary)
    print(
        "pass:  "
        f"{summary['output_tax'] == 2740.0 and summary['eligible_itc'] == 360.0 and summary['net_liability'] == 2380.0}"
    )
