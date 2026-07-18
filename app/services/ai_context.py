"""Format pipeline output as LLM context — explain only, never recalculate."""

from __future__ import annotations

import json
from datetime import date, datetime


def build_ai_context(pipeline_result: dict) -> str:
    """Serialize pipeline results into a compact context block for Gemini."""
    payload = {
        "period": pipeline_result.get("period"),
        "as_of": pipeline_result.get("as_of"),
        "business_state": pipeline_result.get("business_state"),
        "gst": pipeline_result.get("gst"),
        "tds": pipeline_result.get("tds"),
        "action_summary": pipeline_result.get("action_summary"),
        "compliance_calendar": _serialize_calendar(
            pipeline_result.get("compliance_calendar", {})
        ),
        "top_actions": pipeline_result.get("actions", [])[:8],
        "match_overview": _serialize_matches(pipeline_result.get("matches", [])),
        "category_breakdown": _category_breakdown(
            pipeline_result.get("transactions", [])
        ),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_fallback_chat_reply(message: str, pipeline_result: dict) -> str:
    """Answer common chat questions from precomputed pipeline data."""
    lowered = message.lower()
    gst = pipeline_result.get("gst", {})
    tds = pipeline_result.get("tds", {})
    actions = pipeline_result.get("action_summary", {})
    calendar = pipeline_result.get("compliance_calendar", {})
    period = pipeline_result.get("period", "this period")

    if any(word in lowered for word in ("gst", "itc", "liability", "tax payable")):
        return (
            f"For {period}, your GST output tax is ₹{gst.get('output_tax', 0):,.2f}. "
            f"Eligible input tax credit is ₹{gst.get('eligible_itc', 0):,.2f}, so estimated "
            f"net GST payable is ₹{gst.get('net_liability', 0):,.2f}. "
            f"This is based on {gst.get('outward_invoice_count', 0)} sales and "
            f"{gst.get('purchase_invoice_count', 0)} purchase invoices in the period."
        )

    if any(word in lowered for word in ("tds", "deduct", "deposit", "challan")):
        by_section = tds.get("by_section") or {}
        section_lines = ", ".join(
            f"{section}: ₹{amount:,.2f}" for section, amount in by_section.items()
        )
        section_text = f" By section: {section_lines}." if section_lines else ""
        return (
            f"For {period}, TDS deductible is ₹{tds.get('tds_deductible', 0):,.2f}, "
            f"deposited ₹{tds.get('tds_deposited', 0):,.2f}, and "
            f"₹{tds.get('pending_deposit', 0):,.2f} is still pending deposit."
            f"{section_text} Check the Action Center for payments needing review."
        )

    if any(word in lowered for word in ("deadline", "due", "calendar", "filing", "gstr")):
        upcoming = calendar.get("upcoming", [])
        overdue = calendar.get("overdue", [])
        if not upcoming and not overdue:
            return f"No filing deadlines are flagged for {period} in the next 7 days."
        lines = [f"Compliance calendar for {period}:"]
        for item in overdue[:3]:
            lines.append(f"- Overdue: {item['title']} (due {item['due_date']})")
        for item in upcoming[:3]:
            lines.append(
                f"- Upcoming: {item['title']} on {item['due_date']} "
                f"({item.get('days_until', '?')} days away)"
            )
        return "\n".join(lines)

    if any(word in lowered for word in ("action", "flag", "compliance", "issue")):
        top_actions = pipeline_result.get("actions", [])[:5]
        lines = [
            f"There are {actions.get('total', 0)} compliance actions for {period} "
            f"({actions.get('by_severity', {}).get('high', 0)} high priority)."
        ]
        for action in top_actions:
            lines.append(f"- [{action.get('severity', 'info').upper()}] {action.get('title')}")
        return "\n".join(lines)

    if any(word in lowered for word in ("match", "reconcile", "reconciliation")):
        stats = pipeline_result.get("match_stats", {})
        return (
            f"Reconciliation for {period}: {stats.get('auto', 0)} auto-matched, "
            f"{stats.get('review', 0)} need review, and {stats.get('unmatched', 0)} unmatched "
            f"sales invoices out of {stats.get('total', 0)} total."
        )

    return build_fallback_summary(pipeline_result)


def build_fallback_summary(pipeline_result: dict) -> str:
    """Deterministic summary when Gemini is unavailable."""
    gst = pipeline_result.get("gst", {})
    tds = pipeline_result.get("tds", {})
    actions = pipeline_result.get("action_summary", {})
    calendar = pipeline_result.get("compliance_calendar", {})
    period = pipeline_result.get("period", "this period")

    upcoming = calendar.get("upcoming", [])
    deadline_line = "No filing deadlines in the next 7 days."
    if upcoming:
        next_item = upcoming[0]
        deadline_line = (
            f"Next deadline: {next_item['title']} on {next_item['due_date']} "
            f"({next_item['days_until']} days away)."
        )

    return (
        f"Monthly summary for {period}:\n\n"
        f"GST output tax is ₹{gst.get('output_tax', 0):,.2f}, eligible ITC is "
        f"₹{gst.get('eligible_itc', 0):,.2f}, and estimated net GST payable is "
        f"₹{gst.get('net_liability', 0):,.2f}.\n\n"
        f"TDS deductible is ₹{tds.get('tds_deductible', 0):,.2f}, deposited "
        f"₹{tds.get('tds_deposited', 0):,.2f}, with "
        f"₹{tds.get('pending_deposit', 0):,.2f} still pending deposit.\n\n"
        f"There are {actions.get('total', 0)} compliance actions "
        f"({actions.get('by_severity', {}).get('high', 0)} high priority). "
        f"{deadline_line}"
    )


def _serialize_calendar(calendar: dict) -> dict:
    return {
        "upcoming_count": calendar.get("upcoming_count", 0),
        "overdue_count": calendar.get("overdue_count", 0),
        "upcoming": [_serialize_item(item) for item in calendar.get("upcoming", [])],
        "overdue": [_serialize_item(item) for item in calendar.get("overdue", [])],
    }


def _serialize_item(item: dict) -> dict:
    serialized = dict(item)
    due_date = serialized.get("due_date")
    if isinstance(due_date, (date, datetime)):
        serialized["due_date"] = due_date.isoformat()
    return serialized


def _serialize_matches(matches: list[dict]) -> list[dict]:
    overview: list[dict] = []
    for match in matches:
        invoice = match.get("invoice", {})
        overview.append(
            {
                "invoice_number": invoice.get("invoice_number"),
                "customer_name": invoice.get("customer_name"),
                "status": match.get("status"),
                "confidence": match.get("confidence"),
                "matched": match.get("transaction") is not None,
            }
        )
    return overview


def _category_breakdown(transactions: list[dict]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for transaction in transactions:
        category = transaction.get("category", "Uncategorized")
        breakdown[category] = breakdown.get(category, 0) + 1
    return breakdown
