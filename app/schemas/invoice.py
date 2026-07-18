"""Pydantic contract for invoice dicts consumed by core_engine modules.

OCR / upload parsers should produce JSON matching this schema before persisting
to the database or passing to gst.py, match.py, and compliance_flags.py.

Important: `amount` is the taxable value BEFORE GST (pre-tax base), not the
invoice total inclusive of tax.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_GST_RATES = frozenset({0.0, 5.0, 12.0, 18.0, 28.0})
SupplyType = Literal["B2B", "B2C"]


class InvoiceSchema(BaseModel):
    invoice_number: str
    date: str = Field(description="Invoice date in YYYY-MM-DD format.")
    amount: float = Field(ge=0, description="Taxable value before GST.")
    customer_name: str = ""
    vendor_name: str | None = None
    is_purchase: bool = False
    gstin: str | None = None
    gst_rate: float = 0.0
    place_of_supply: str = ""
    supply_type: SupplyType = "B2C"
    hsn_sac: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if not DATE_PATTERN.match(value):
            raise ValueError("date must be in YYYY-MM-DD format")
        return value

    @field_validator("gst_rate")
    @classmethod
    def validate_gst_rate(cls, value: float) -> float:
        if value not in VALID_GST_RATES:
            raise ValueError(f"gst_rate must be one of {sorted(VALID_GST_RATES)}")
        return value

    @field_validator("supply_type", mode="before")
    @classmethod
    def normalize_supply_type(cls, value: str) -> str:
        return value.strip().upper()

    def to_engine_dict(self) -> dict:
        """Return a plain dict for core_engine functions."""
        return self.model_dump()

    @classmethod
    def from_engine_dict(cls, data: dict) -> InvoiceSchema:
        return cls.model_validate(data)
