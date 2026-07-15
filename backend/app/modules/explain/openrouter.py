"""OpenRouter client for the AI Decision Layer.

Strictly grounded: the model is instructed to explain only the supplied evidence and to
return structured JSON. Any failure returns None so the caller falls back to the offline
grounded narrator — the investigation remains fully usable without AI.
"""
from __future__ import annotations

import json
import re
import time

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are ARGUS's explainability layer inside a bank's security operations centre. "
    "You explain evidence produced by analytical engines; you never detect, invent, or "
    "estimate. Rules: (1) Use ONLY facts present in the provided investigation JSON. "
    "(2) Never introduce customers, amounts, devices, timestamps, or conclusions not in the "
    "data. (3) If information is missing, say so rather than guessing. (4) Write in the calm, "
    "factual tone of an internal incident report. Return STRICT JSON with exactly these keys: "
    "executive_summary, technical_summary, confidence_explanation, evidence_summary, "
    "recommended_action_summary. Output ONLY the JSON object — no markdown, no preamble. "
    "All FIVE keys are REQUIRED and every value must be a non-empty plain-text paragraph."
)

_KEYS = ("executive_summary", "technical_summary", "confidence_explanation",
         "evidence_summary", "recommended_action_summary")


def _grounding_payload(detail: dict) -> dict:
    """Trim the investigation to the fields the model is allowed to reason over."""
    return {
        "code": detail["code"], "title": detail["title"], "category": detail["category"],
        "severity": detail["severity"], "confidence": detail["confidence"],
        "originating_engine": detail["originating_engine"],
        "primary_customer": detail.get("primary_customer"),
        "primary_endpoint": detail.get("primary_endpoint"),
        "vulnerability": detail.get("vulnerability"),
        "business_impact": detail.get("business_impact"),
        "confidence_breakdown": detail.get("confidence_breakdown"),
        "evidence": [{"category": e["category"], "title": e["title"],
                      "description": e["description"]} for e in detail.get("evidence", [])],
        "recommendations": [{"priority": r["priority"], "title": r["title"],
                             "rationale": r["rationale"]} for r in detail.get("recommendations", [])],
        "reconstruction": (detail.get("meta") or {}).get("reconstruction"),
        "predicted_next_step": detail.get("predicted_next_step"),
    }


def generate(detail: dict) -> dict | None:
    if not (settings.ai_enabled and settings.openrouter_api_key):
        return None
    payload = _grounding_payload(detail)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Investigation JSON:\n" + json.dumps(payload, default=str)},
    ]
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://argus.local",
        "X-Title": "ARGUS",
    }

    def _call(use_json_format: bool) -> str:
        body = {"model": settings.openrouter_model, "messages": messages, "temperature": 0.2}
        if use_json_format:
            body["response_format"] = {"type": "json_object"}
        with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
            resp = client.post(f"{settings.openrouter_base_url}/chat/completions",
                               json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    # Thinking models occasionally return an incomplete payload — retry a couple of times
    # before degrading to the offline narrator.
    last_reason = "no response"
    for attempt in range(1, 3):
        try:
            try:
                content = _call(use_json_format=True)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status == 429:
                    last_reason = "rate limited (429)"
                    time.sleep(2)
                    continue
                content = _call(use_json_format=False)  # model may reject response_format
            data = _extract_json(content)
            if data and all(k in data and isinstance(data[k], str) and data[k].strip()
                            for k in _KEYS):
                return {k: data[k].strip() for k in _KEYS}
            last_reason = "incomplete JSON payload"
        except Exception as exc:  # noqa: BLE001 — degrade to offline on any error
            last_reason = str(exc)[:80]
        logger.warning("Live AI attempt %d unusable (%s); retrying...", attempt, last_reason)
    logger.warning("Live AI unavailable (%s); using offline narrator.", last_reason)
    return None


def _extract_json(text: str) -> dict | None:
    """Tolerant JSON extraction: handles ```json fences and surrounding prose."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE).strip()
    try:
        return json.loads(t)
    except Exception:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(t[start:end + 1])
            except Exception:
                return None
    return None
