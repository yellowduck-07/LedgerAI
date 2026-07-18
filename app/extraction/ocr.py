"""Gemini Vision OCR for invoice PDFs and images.

Returns structured invoice dicts validated against InvoiceSchema.
Tax calculations remain in core_engine — OCR only extracts fields.
"""

from __future__ import annotations

import json
import re

from app.config import GEMINI_API_KEY, GEMINI_OCR_MODEL
from app.schemas.invoice import InvoiceSchema

OCR_SYSTEM_INSTRUCTION = """You extract structured data from Indian tax invoices.
Return ONLY a single JSON object with these fields:
- invoice_number (string)
- date (YYYY-MM-DD)
- amount (number, taxable value BEFORE GST, not grand total with tax)
- customer_name (string, empty for purchase bills)
- vendor_name (string or null, set for purchase bills from vendor)
- is_purchase (boolean, true when the uploaded bill is from a vendor/supplier)
- gstin (string or null, 15-char GSTIN if visible)
- gst_rate (number, one of 0, 5, 12, 18, 28)
- place_of_supply (string, Indian state name or code)
- supply_type (string, B2B or B2C)
- hsn_sac (string or null)

Rules:
- Prefer taxable value / taxable amount over invoice total including GST.
- Use null for missing optional fields, not empty strings except customer_name.
- Do not include markdown fences or commentary.
"""

OCR_PROMPT = (
    "Extract invoice fields from this document and return the JSON object only."
)


def extract_invoice_with_ocr(content: bytes, filename: str) -> dict:
    """Run Gemini Vision OCR and validate against InvoiceSchema."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is required for OCR on scanned PDFs and images. "
            "Set it in your environment or Render dashboard."
        )

    mime_type = _mime_type_for_filename(filename)
    raw_json = _call_gemini_ocr(content, mime_type)
    payload = _parse_json_response(raw_json)
    return InvoiceSchema.from_engine_dict(_normalize_payload(payload)).to_engine_dict()


def _call_gemini_ocr(content: bytes, mime_type: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        GEMINI_OCR_MODEL,
        system_instruction=OCR_SYSTEM_INSTRUCTION,
    )
    response = model.generate_content(
        [
            OCR_PROMPT,
            {"mime_type": mime_type, "data": content},
        ],
        generation_config={"response_mime_type": "application/json"},
    )
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("Gemini OCR returned an empty response.")
    return text.strip()


def _parse_json_response(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("OCR response must be a JSON object.")
    return payload


def _normalize_payload(payload: dict) -> dict:
    normalized = {
        "invoice_number": payload.get("invoice_number") or "INV-OCR",
        "date": payload.get("date") or "2026-01-01",
        "amount": float(payload.get("amount") or 0),
        "customer_name": payload.get("customer_name") or "",
        "vendor_name": payload.get("vendor_name"),
        "is_purchase": bool(payload.get("is_purchase", False)),
        "gstin": payload.get("gstin"),
        "gst_rate": float(payload.get("gst_rate") or 0),
        "place_of_supply": payload.get("place_of_supply") or "Maharashtra",
        "supply_type": payload.get("supply_type") or "B2C",
        "hsn_sac": payload.get("hsn_sac"),
    }
    if normalized["supply_type"]:
        normalized["supply_type"] = str(normalized["supply_type"]).upper()
    return normalized


def _mime_type_for_filename(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return "application/pdf"
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return "image/jpeg"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"
