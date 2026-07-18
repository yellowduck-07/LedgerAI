"""Parse invoice uploads from JSON, PDF, images, or plain text."""

from __future__ import annotations

import io
import json
import re

from app.extraction.ocr import extract_invoice_with_ocr
from app.schemas.invoice import InvoiceSchema

GSTIN_PATTERN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
AMOUNT_PATTERNS = (
    re.compile(r"taxable\s*(?:amount|value)?[:\s]*₹?\s*([\d,]+(?:\.\d+)?)", re.I),
    re.compile(r"(?:total|amount)[:\s]*₹?\s*([\d,]+(?:\.\d+)?)", re.I),
)
GST_RATE_PATTERN = re.compile(r"gst\s*rate[:\s]*(\d+(?:\.\d+)?)\s*%?", re.I)
HSN_PATTERN = re.compile(r"(?:hsn|sac|hsn/sac)[:\s]*([0-9]{4,8})", re.I)
CUSTOMER_PATTERN = re.compile(r"customer[:\s]*(.+)", re.I)
VENDOR_PATTERN = re.compile(r"vendor[:\s]*(.+)", re.I)
PLACE_PATTERN = re.compile(r"place\s*of\s*supply[:\s]*(.+)", re.I)
PURCHASE_PATTERN = re.compile(r"invoice\s*type[:\s]*(purchase|sales)", re.I)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
PDF_EXTENSION = ".pdf"


def parse_invoice_upload(content: bytes, filename: str) -> list[dict]:
    return parse_invoice_upload_detailed(content, filename)["invoices"]


def parse_invoice_upload_detailed(content: bytes, filename: str) -> dict:
    """Parse upload and report which extraction path was used."""
    lowered = filename.lower()

    if lowered.endswith(".json"):
        invoices = parse_invoices_json(content)
        return {
            "invoices": invoices,
            "extraction_method": "json",
            "extraction_methods": ["json"] * len(invoices),
        }

    if _has_extension(lowered, IMAGE_EXTENSIONS):
        invoice = extract_invoice_with_ocr(content, filename)
        return {
            "invoices": [invoice],
            "extraction_method": "gemini_ocr",
            "extraction_methods": ["gemini_ocr"],
        }

    if lowered.endswith(PDF_EXTENSION):
        return _parse_pdf_upload(content, filename)

    invoice = parse_invoice_text(content.decode("utf-8", errors="ignore"))
    return {
        "invoices": [invoice],
        "extraction_method": "text",
        "extraction_methods": ["text"],
    }


def _parse_pdf_upload(content: bytes, filename: str) -> dict:
    text = _try_extract_pdf_text(content)
    if text and _text_is_rich_enough(text):
        invoice = parse_invoice_text(text)
        return {
            "invoices": [invoice],
            "extraction_method": "pdf_text",
            "extraction_methods": ["pdf_text"],
            "raw_text_preview": text[:500],
        }

    invoice = extract_invoice_with_ocr(content, filename)
    return {
        "invoices": [invoice],
        "extraction_method": "gemini_ocr",
        "extraction_methods": ["gemini_ocr"],
        "raw_text_preview": text[:500] if text else None,
    }


def parse_invoices_json(content: str | bytes) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    payload = json.loads(content)
    if isinstance(payload, dict):
        payload = [payload]

    return [InvoiceSchema.from_engine_dict(item).to_engine_dict() for item in payload]


def _try_extract_pdf_text(content: bytes) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        return text or None
    except Exception:
        return None


def _text_is_rich_enough(text: str) -> bool:
    if len(text) < 40:
        return False
    has_amount = any(pattern.search(text) for pattern in AMOUNT_PATTERNS)
    has_date = DATE_PATTERN.search(text) is not None
    has_invoice_ref = re.search(r"invoice", text, re.I) is not None
    return has_amount and has_date and has_invoice_ref


def parse_invoice_text(text: str) -> dict:
    """Best-effort regex extraction from raw invoice text or PDF text layer."""
    upper_text = text.upper()
    gstin_match = GSTIN_PATTERN.search(upper_text)
    date_match = DATE_PATTERN.search(text)
    amount = _extract_amount(text)
    gst_rate = _extract_gst_rate(text, bool(gstin_match))
    is_purchase = _extract_is_purchase(text)
    customer_name, vendor_name = _extract_party_names(text, is_purchase)

    invoice = InvoiceSchema.from_engine_dict(
        {
            "invoice_number": _extract_invoice_number(text),
            "date": date_match.group(1) if date_match else "2026-01-01",
            "amount": amount,
            "customer_name": customer_name,
            "vendor_name": vendor_name,
            "is_purchase": is_purchase,
            "gstin": gstin_match.group(0) if gstin_match else None,
            "gst_rate": gst_rate,
            "place_of_supply": _extract_place_of_supply(text),
            "supply_type": "B2B" if gstin_match else "B2C",
            "hsn_sac": _extract_hsn(text),
        }
    )
    return invoice.to_engine_dict()


def _has_extension(filename: str, extensions: set[str]) -> bool:
    return any(filename.endswith(ext) for ext in extensions)


def _extract_amount(text: str) -> float:
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1).replace(",", ""))
    return 0.0


def _extract_gst_rate(text: str, has_gstin: bool) -> float:
    match = GST_RATE_PATTERN.search(text)
    if match:
        return float(match.group(1))
    return 18.0 if has_gstin else 0.0


def _extract_hsn(text: str) -> str | None:
    match = HSN_PATTERN.search(text)
    return match.group(1) if match else None


def _extract_place_of_supply(text: str) -> str:
    match = PLACE_PATTERN.search(text)
    if match:
        return match.group(1).strip().split("\n")[0][:64]
    return "Maharashtra"


def _extract_is_purchase(text: str) -> bool:
    match = PURCHASE_PATTERN.search(text)
    if match:
        return match.group(1).casefold() == "purchase"
    return "vendor:" in text.casefold() and "customer:" not in text.casefold()


def _extract_party_names(text: str, is_purchase: bool) -> tuple[str, str | None]:
    customer_match = CUSTOMER_PATTERN.search(text)
    vendor_match = VENDOR_PATTERN.search(text)

    customer_name = customer_match.group(1).strip().split("\n")[0] if customer_match else ""
    vendor_name = vendor_match.group(1).strip().split("\n")[0] if vendor_match else None

    if is_purchase:
        return "", vendor_name
    return customer_name, None


def _extract_invoice_number(text: str) -> str:
    patterns = (
        r"invoice\s*(?:no|number|#)[:\s]*([A-Z0-9-]+)",
        r"inv[-\s]?([A-Z0-9-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).upper()
    return "INV-UPLOAD"
