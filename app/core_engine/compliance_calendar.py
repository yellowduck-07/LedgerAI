"""Static compliance deadline calendar for Indian SMEs.

Provides upcoming statutory due dates (GST, TDS, advance tax) without LLM or
external APIs. Dashboard and Action Center can surface "due in N days" alerts.

Input:

    as_of: "YYYY-MM-DD"  # reference date, usually today
    within_days: int     # look-ahead window (default 7)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

DEFAULT_LOOKAHEAD_DAYS = 7

# day_of_month applies to the month AFTER the tax period for monthly items.
MONTHLY_DEADLINES: tuple[dict, ...] = (
    {
        "id": "gstr1",
        "title": "GSTR-1 filing",
        "category": "GST",
        "day_of_month": 11,
        "description": "Outward supply return for previous tax period.",
    },
    {
        "id": "gstr3b",
        "title": "GSTR-3B filing & payment",
        "category": "GST",
        "day_of_month": 20,
        "description": "Summary return and GST payment for previous tax period.",
    },
    {
        "id": "tds_deposit",
        "title": "TDS deposit",
        "category": "TDS",
        "day_of_month": 7,
        "description": "Deposit tax deducted during previous month.",
    },
)

# (month, day) each financial year — advance tax installments.
QUARTERLY_DEADLINES: tuple[dict, ...] = (
    {
        "id": "advance_tax_q1",
        "title": "Advance tax — Q1 installment",
        "category": "Income Tax",
        "month": 6,
        "day": 15,
        "description": "First advance tax installment (15% of estimated liability).",
    },
    {
        "id": "advance_tax_q2",
        "title": "Advance tax — Q2 installment",
        "category": "Income Tax",
        "month": 9,
        "day": 15,
        "description": "Second advance tax installment (45% cumulative).",
    },
    {
        "id": "advance_tax_q3",
        "title": "Advance tax — Q3 installment",
        "category": "Income Tax",
        "month": 12,
        "day": 15,
        "description": "Third advance tax installment (75% cumulative).",
    },
    {
        "id": "advance_tax_q4",
        "title": "Advance tax — Q4 installment",
        "category": "Income Tax",
        "month": 3,
        "day": 15,
        "description": "Final advance tax installment (100% of estimated liability).",
    },
)


def get_upcoming_deadlines(
    as_of: str,
    within_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> list[dict]:
    """Return deadlines due within the next `within_days` days (inclusive)."""
    reference = _parse_date(as_of)
    window_end = reference + timedelta(days=within_days)
    upcoming: list[dict] = []

    for deadline in _all_deadline_occurrences(reference, window_end):
        days_until = (deadline["due_date"] - reference).days
        if 0 <= days_until <= within_days:
            upcoming.append(
                {
                    **deadline,
                    "days_until": days_until,
                    "status": "due_soon",
                }
            )

    return sorted(upcoming, key=lambda item: (item["due_date"], item["id"]))


def get_overdue_deadlines(as_of: str, lookback_days: int = 30) -> list[dict]:
    """Return deadlines that passed within the recent lookback window."""
    reference = _parse_date(as_of)
    window_start = reference - timedelta(days=lookback_days)
    overdue: list[dict] = []

    for deadline in _all_deadline_occurrences(window_start, reference):
        if deadline["due_date"] < reference:
            overdue.append(
                {
                    **deadline,
                    "days_until": (deadline["due_date"] - reference).days,
                    "status": "overdue",
                }
            )

    return sorted(overdue, key=lambda item: item["due_date"], reverse=True)


def get_compliance_snapshot(
    as_of: str,
    within_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> dict:
    """Summary payload for dashboard widgets."""
    upcoming = get_upcoming_deadlines(as_of, within_days)
    overdue = get_overdue_deadlines(as_of, lookback_days=within_days)

    return {
        "as_of": as_of,
        "within_days": within_days,
        "upcoming_count": len(upcoming),
        "overdue_count": len(overdue),
        "upcoming": upcoming,
        "overdue": overdue,
    }


def _all_deadline_occurrences(window_start: date, window_end: date) -> list[dict]:
    occurrences: list[dict] = []

    for year in range(window_start.year - 1, window_end.year + 2):
        for template in MONTHLY_DEADLINES:
            for month in range(1, 13):
                due = _safe_date(year, month, template["day_of_month"])
                if window_start <= due <= window_end:
                    tax_period = _previous_month(due)
                    occurrences.append(
                        {
                            "id": template["id"],
                            "title": template["title"],
                            "category": template["category"],
                            "description": template["description"],
                            "due_date": due,
                            "tax_period": tax_period,
                        }
                    )

        for template in QUARTERLY_DEADLINES:
            due = _safe_date(year, template["month"], template["day"])
            if window_start <= due <= window_end:
                occurrences.append(
                    {
                        "id": template["id"],
                        "title": template["title"],
                        "category": template["category"],
                        "description": template["description"],
                        "due_date": due,
                        "tax_period": f"FY {year if template['month'] >= 4 else year - 1}-{str(year)[-2:]}",
                    }
                )

    return occurrences


def _previous_month(due_date: date) -> str:
    if due_date.month == 1:
        period = date(due_date.year - 1, 12, 1)
    else:
        period = date(due_date.year, due_date.month - 1, 1)
    return period.strftime("%Y-%m")


def _safe_date(year: int, month: int, day: int) -> date:
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


if __name__ == "__main__":
    test_cases = [
        (
            "GSTR-3B due within 7 days",
            "2026-01-15",
            7,
            {"expect_id": "gstr3b", "expect_days_until": 5},
        ),
        (
            "TDS deposit due within 7 days",
            "2026-02-03",
            7,
            {"expect_id": "tds_deposit", "expect_days_until": 4},
        ),
        (
            "Advance tax Q4 in window",
            "2026-03-10",
            7,
            {"expect_id": "advance_tax_q4", "expect_days_until": 5},
        ),
        (
            "Nothing urgent mid-month gap",
            "2026-01-25",
            7,
            {"expect_count_max": 2},
        ),
    ]

    for label, as_of, within_days, expected in test_cases:
        upcoming = get_upcoming_deadlines(as_of, within_days)
        snapshot = get_compliance_snapshot(as_of, within_days)

        print(f"=== {label} ===")
        print(f"as_of:     {as_of}")
        print(f"upcoming:  {upcoming}")

        if "expect_id" in expected:
            matched = next((item for item in upcoming if item["id"] == expected["expect_id"]), None)
            passed = matched is not None and matched["days_until"] == expected["expect_days_until"]
        else:
            passed = len(upcoming) <= expected["expect_count_max"]

        print(f"snapshot:  upcoming={snapshot['upcoming_count']} overdue={snapshot['overdue_count']}")
        print(f"pass:      {passed}")
        print()

    overdue = get_overdue_deadlines("2026-01-15", lookback_days=10)
    print("=== Overdue sample (2026-01-15) ===")
    print(overdue[:2])
    print(f"pass:      {any(item['id'] == 'gstr1' for item in overdue)}")
