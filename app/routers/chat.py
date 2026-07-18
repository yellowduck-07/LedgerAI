"""Gemini-powered Virtual CA chat and monthly summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import DEFAULT_BUSINESS_STATE
from app.core_engine.pipeline import run_pipeline
from app.database import get_db
from app.services.ai_context import build_ai_context
from app.services.data_loader import load_period_data
from app.services.gemini_client import generate_chat_reply, generate_summary

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = Field(description="user or assistant")
    content: str


class ChatRequest(BaseModel):
    message: str
    period: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    source: str
    period: str | None


class SummaryResponse(BaseModel):
    summary: str
    source: str
    period: str | None


def _run_context_pipeline(
    db: Session,
    period: str | None,
) -> tuple[dict, str]:
    from app.services.data_loader import get_data_status

    status = get_data_status(db)
    if not status["analytics_ready"]:
        raise ValueError(
            "Upload at least one invoice and one bank transaction before using AI features."
        )

    invoices, transactions = load_period_data(db, period)
    pipeline_result = run_pipeline(
        invoices,
        transactions,
        business_state=DEFAULT_BUSINESS_STATE,
        period=period,
        as_of=f"{period}-28" if period else None,
    )
    return pipeline_result, build_ai_context(pipeline_result)


@router.get("/summary", response_model=SummaryResponse)
def monthly_summary(
    period: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        pipeline_result, context = _run_context_pipeline(db, period)
    except ValueError as exc:
        return SummaryResponse(summary=str(exc), source="empty", period=period)

    result = generate_summary(context, pipeline_result)
    return SummaryResponse(
        summary=result["summary"],
        source=result["source"],
        period=period or pipeline_result.get("period"),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        pipeline_result, context = _run_context_pipeline(db, request.period)
    except ValueError as exc:
        return ChatResponse(reply=str(exc), source="empty", period=request.period)

    history = [message.model_dump() for message in request.history]
    result = generate_chat_reply(
        request.message,
        context,
        history,
        pipeline_result=pipeline_result,
    )

    return ChatResponse(
        reply=result["reply"],
        source=result["source"],
        period=request.period or pipeline_result.get("period"),
    )
