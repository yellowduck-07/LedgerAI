"""Shared pipeline access for API routers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import DEFAULT_BUSINESS_STATE
from app.core_engine.pipeline import run_pipeline
from app.services.data_loader import load_period_data


def get_pipeline_result(db: Session, period: str | None = None) -> dict:
    invoices, transactions = load_period_data(db, period)
    as_of = f"{period}-28" if period else None
    return run_pipeline(
        invoices,
        transactions,
        business_state=DEFAULT_BUSINESS_STATE,
        period=period,
        as_of=as_of,
    )