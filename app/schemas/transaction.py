"""Pydantic contract for bank transaction dicts consumed by core_engine modules.

CSV upload parsers should produce rows matching this schema. The `category` field
is optional on ingest — pipeline.py will call categorize.py when it is absent.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
Direction = Literal["debit", "credit"]


class TransactionSchema(BaseModel):
    description: str
    amount: float = Field(ge=0)
    date: str = Field(description="Transaction date in YYYY-MM-DD format.")
    direction: Direction
    category: str | None = None
    vendor_name: str | None = None
    pan_available: bool = False

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if not DATE_PATTERN.match(value):
            raise ValueError("date must be in YYYY-MM-DD format")
        return value

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, value: str) -> str:
        return value.strip().casefold()

    def to_engine_dict(self) -> dict:
        """Return a plain dict for core_engine functions."""
        data = self.model_dump()
        if data.get("category") is None:
            data.pop("category", None)
        return data

    @classmethod
    def from_engine_dict(cls, data: dict) -> TransactionSchema:
        return cls.model_validate(data)
