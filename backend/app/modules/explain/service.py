"""ExplainService — generate, validate and persist grounded AI narratives."""
from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import AINarrative, Investigation
from app.modules.investigations import InvestigationService
from . import offline, openrouter

logger = get_logger(__name__)


class ExplainService:
    def __init__(self, session: Session):
        self.s = session
        self.inv = InvestigationService(session)

    def generate(self, code: str, prefer_offline: bool = False) -> dict:
        detail = self.inv.detail(code)
        inv = self.s.scalar(select(Investigation).where(Investigation.code == code))

        started = time.perf_counter()
        # prefer_offline keeps bulk rebuilds instant; the on-demand API uses the live model.
        narratives = None if prefer_offline else openrouter.generate(detail)
        live_provider = "gemini" if "googleapis" in settings.openrouter_base_url else "openrouter"
        provider, model, grounded = live_provider, settings.openrouter_model, True
        if narratives is None or not self._passes_guard(narratives, detail):
            narratives = offline.generate_all(detail)
            provider, model = "offline", "argus-grounded-narrator-v1"
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        # Deactivate previous narratives; keep history.
        prev = self.s.scalars(select(AINarrative).where(
            AINarrative.investigation_id == inv.id, AINarrative.is_active == True)).all()  # noqa: E712
        regen = 0
        for p in prev:
            p.is_active = False
            regen = max(regen, p.regeneration_count + 1)

        row = AINarrative(
            investigation_id=inv.id, provider=provider, model_id=model, prompt_version="v1",
            executive_summary=narratives["executive_summary"],
            technical_summary=narratives["technical_summary"],
            confidence_explanation=narratives["confidence_explanation"],
            evidence_summary=narratives["evidence_summary"],
            recommended_action_summary=narratives["recommended_action_summary"],
            structured_refs={"evidence_count": detail["evidence_count"]},
            grounded=grounded, generation_ms=elapsed_ms, regeneration_count=regen, is_active=True,
        )
        self.s.add(row)
        self.s.commit()
        logger.info("AI narrative for %s via %s (%d ms)", code, provider, elapsed_ms)
        return {"investigation": code, "provider": provider, "model": model,
                "generation_ms": elapsed_ms}

    @staticmethod
    def _passes_guard(narratives: dict, detail: dict) -> bool:
        """Basic hallucination guard: the executive summary must reference real anchors."""
        text = " ".join(narratives.values()).lower()
        anchors = []
        if detail.get("primary_customer"):
            anchors.append(detail["primary_customer"]["ref"].lower())
        if detail.get("vulnerability"):
            anchors.append(detail["vulnerability"]["ref"].lower())
        # If we have anchors, at least one should appear; always require non-trivial length.
        if len(text) < 200:
            return False
        if anchors and not any(a in text for a in anchors):
            return False
        return True
