"""
LLM abstraction for AI Insights V2.

Uses only the existing Ollama-compatible local endpoint.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _parse_model_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


class AIService:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.primary_model = settings.OLLAMA_MODEL or "llama3.2:3b"
        self.fallback_models = _parse_model_list(settings.OLLAMA_FALLBACK_MODELS)

    async def _call_ollama(self, prompt: str) -> Optional[str]:
        model_candidates = [self.primary_model, *self.fallback_models]
        timeout = httpx.Timeout(timeout=120.0, connect=20.0, read=120.0, write=20.0, pool=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for model in model_candidates:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_predict": 350,
                    },
                }
                try:
                    response = await client.post(f"{self.base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    content = response.json().get("message", {}).get("content", "").strip()
                    if content:
                        return content
                except Exception:
                    logger.warning("Ollama request failed for model=%s", model, exc_info=True)
        return None

    @staticmethod
    def _build_prompt(structured_data: dict[str, Any]) -> str:
        compact = json.dumps(structured_data, separators=(",", ":"), ensure_ascii=True, default=str)
        return (
            "Given the following student performance data:\n"
            f"{compact}\n\n"
            "Generate:\n\n"
            "1. Strengths\n"
            "2. Weaknesses\n"
            "3. Improvement suggestions\n"
            "4. Study plan\n\n"
            "Keep output concise and structured."
        )

    @staticmethod
    def _coerce_recommendations(text: str) -> dict[str, Any]:
        # Best-case: model returned JSON.
        try:
            raw = text.strip()
            if raw.startswith("{") and raw.endswith("}"):
                parsed = json.loads(raw)
                return {
                    "strengths": parsed.get("strengths", []),
                    "weaknesses": parsed.get("weaknesses", []),
                    "improvement_suggestions": parsed.get("improvement_suggestions", []),
                    "study_plan": parsed.get("study_plan", []),
                }
        except Exception:
            pass

        # Safe fallback: keep raw text and let UI render as narrative.
        return {
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": [],
            "study_plan": [],
            "raw": text,
        }

    async def generate_insight(self, structured_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        prompt = self._build_prompt(structured_data)
        text = await self._call_ollama(prompt)
        if not text:
            return None
        return {
            "insight_text": text,
            "recommendations": self._coerce_recommendations(text),
        }


ai_service = AIService()

