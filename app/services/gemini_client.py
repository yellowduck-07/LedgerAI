"""Gemini client for Virtual CA chat and summary — explain-only, no tax math."""

from __future__ import annotations

from app.config import GEMINI_API_KEY, GEMINI_MODEL
import logging

from app.services.ai_context import build_fallback_chat_reply, build_fallback_summary

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are LedgerAI, a Virtual CA assistant for Indian small businesses and shop owners.

Rules:
- Use ONLY the financial context provided below. Never invent numbers.
- Do NOT recalculate GST, TDS, or ITC — the context already contains final computed values.
- Explain clearly in plain English with ₹ amounts from the context.
- Mention actionable compliance items when relevant.
- Keep answers concise unless the user asks for detail.
- If context is missing a value, say you do not have that data yet.
"""


def generate_summary(context: str, pipeline_result: dict) -> dict:
    """Return a monthly narrative summary."""
    prompt = (
        "Write a concise monthly financial summary in 3 short paragraphs for a shop owner.\n"
        "Cover: GST liability, ITC, TDS status, top compliance actions, and upcoming deadlines.\n"
        "Use ₹ and keep a helpful Virtual CA tone.\n\n"
        f"FINANCIAL CONTEXT:\n{context}"
    )

    text = _generate_text(prompt)
    source = "gemini"
    if text is None:
        text = build_fallback_summary(pipeline_result)
        source = "fallback"

    return {
        "summary": text,
        "source": source,
    }


def generate_chat_reply(
    message: str,
    context: str,
    history: list[dict] | None = None,
    pipeline_result: dict | None = None,
) -> dict:
    """Answer a user question using precomputed pipeline context."""
    history = history or []
    history_text = _format_history(history)

    prompt = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"FINANCIAL CONTEXT:\n{context}\n\n"
        f"{history_text}"
        f"USER QUESTION:\n{message}\n\n"
        "Answer as LedgerAI:"
    )

    text = _generate_text(prompt, system_instruction=SYSTEM_INSTRUCTION)
    source = "gemini"
    if text is None:
        if pipeline_result:
            text = build_fallback_chat_reply(message, pipeline_result)
        else:
            text = (
                "I cannot reach Gemini right now. Based on the computed data, please check "
                "the dashboard for GST net liability, TDS pending deposit, and the Action "
                "Center for compliance flags."
            )
        source = "fallback"

    return {
        "reply": text,
        "source": source,
    }


def _generate_text(prompt: str, system_instruction: str | None = None) -> str | None:
    if not GEMINI_API_KEY:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=system_instruction or SYSTEM_INSTRUCTION,
        )
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        if text:
            return text.strip()
    except Exception as exc:
        logger.warning("Gemini request failed: %s", exc)
        return None

    return None


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""

    lines = ["CONVERSATION HISTORY:"]
    for turn in history[-6:]:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        lines.append(f"{role.upper()}: {content}")
    lines.append("")
    return "\n".join(lines) + "\n"
