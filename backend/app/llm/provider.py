from __future__ import annotations

import json
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.models import ApiUsage


class SharedLLMProvider:
    """Single shared LLM provider supporting Gemini, OpenAI, Claude, Ollama, and No-LLM deterministic mode."""

    SUPPORTED_PROVIDERS = ("none", "gemini", "openai", "claude", "ollama")

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.settings = get_settings()
        self.provider = (provider or self.settings.llm_provider or "none").strip().lower()
        if self.provider not in self.SUPPORTED_PROVIDERS:
            self.provider = "none"
        self.model = model or self.settings.llm_model or self._default_model(self.provider)

    @staticmethod
    def _default_model(provider: str) -> str:
        defaults = {
            "none": "deterministic-rule-engine-v1",
            "gemini": "gemini-2.5-flash",
            "openai": "gpt-4o-mini",
            "claude": "claude-3-5-sonnet-latest",
            "ollama": "llama3.1:8b",
        }
        return defaults.get(provider, "deterministic-rule-engine-v1")

    def is_configured(self) -> bool:
        if self.provider == "none":
            return True
        if self.provider == "gemini":
            return bool(self.settings.gemini_api_key)
        if self.provider == "openai":
            return bool(self.settings.openai_api_key)
        if self.provider == "claude":
            return bool(self.settings.anthropic_api_key)
        if self.provider == "ollama":
            return bool(self.settings.ollama_base_url)
        return False

    def generate_json(
        self,
        db: Session | None,
        system_prompt: str,
        user_prompt: str,
        fallback_payload: dict[str, Any],
        operation: str = "llm_generation",
        timeout: float = 20.0,
    ) -> dict[str, Any]:
        """Generate structured JSON from the configured LLM or fall back cleanly to deterministic output."""
        if self.provider == "none" or not self.is_configured():
            return {
                **fallback_payload,
                "_llm_meta": {
                    "provider": "none",
                    "model": "deterministic-rule-engine-v1",
                    "fallback_used": False,
                },
            }

        start = time.perf_counter()
        try:
            raw_text, tokens = self._dispatch_request(system_prompt, user_prompt, timeout=timeout)
            latency_ms = (time.perf_counter() - start) * 1000.0
            parsed = self._extract_json(raw_text)
            if db is not None:
                db.add(
                    ApiUsage(
                        provider=f"llm:{self.provider}",
                        endpoint=self.model,
                        operation=operation,
                        units_or_tokens=tokens,
                        estimated_cost_usd=0.0,
                        status_code=200,
                        success=True,
                        latency_ms=round(latency_ms, 2),
                    )
                )
                db.flush()
            parsed["_llm_meta"] = {
                "provider": self.provider,
                "model": self.model,
                "fallback_used": False,
            }
            return parsed
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            if db is not None:
                db.add(
                    ApiUsage(
                        provider=f"llm:{self.provider}",
                        endpoint=self.model,
                        operation=operation,
                        units_or_tokens=0,
                        estimated_cost_usd=0.0,
                        status_code=500,
                        success=False,
                        latency_ms=round(latency_ms, 2),
                        error_detail=str(exc)[:500],
                    )
                )
                db.flush()
            return {
                **fallback_payload,
                "_llm_meta": {
                    "provider": "none",
                    "model": "deterministic-rule-engine-v1",
                    "fallback_used": True,
                    "error": str(exc),
                },
            }

    def _dispatch_request(self, system_prompt: str, user_prompt: str, timeout: float = 20.0) -> tuple[str, int]:
        with httpx.Client(timeout=timeout) as client:
            if self.provider == "openai":
                resp = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                    json={
                        "model": self.model,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.2,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                tokens = int(data.get("usage", {}).get("total_tokens", 250))
                return text, tokens

            if self.provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
                resp = client.post(
                    url,
                    params={"key": self.settings.gemini_api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                tokens = int(data.get("usageMetadata", {}).get("totalTokenCount", 250))
                return text, tokens

            if self.provider == "claude":
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 1024,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["content"][0]["text"]
                usage = data.get("usage", {})
                tokens = int(usage.get("input_tokens", 100)) + int(usage.get("output_tokens", 150))
                return text, tokens

            if self.provider == "ollama":
                base = self.settings.ollama_base_url.rstrip("/")
                resp = client.post(
                    f"{base}/api/generate",
                    json={
                        "model": self.model,
                        "system": system_prompt,
                        "prompt": user_prompt,
                        "format": "json",
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "{}"), int(data.get("eval_count", 200))

        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    @staticmethod
    def _extract_json(raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object.")
        return parsed
