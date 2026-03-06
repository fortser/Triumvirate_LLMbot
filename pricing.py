"""Менеджер тарифов и расчёта стоимости LLM-вызовов (OpenRouter).

Загружает цены из OpenRouter /api/v1/models, считает стоимость per-move
по prompt/completion/reasoning токенам.

Зависимости: httpx.
Зависимые: bot_runner.
"""
from __future__ import annotations

from typing import Any

import httpx


class PricingManager:
    """Fetches and caches model pricing from OpenRouter /api/v1/models.

    Prices are stored as USD per 1 000 000 tokens (industry-standard format).
    For non-OpenRouter providers, returns zeroes.
    """

    def __init__(self) -> None:
        self._pricing: dict[str, float] = {}
        self._raw_model_data: dict | None = None
        self._source: str = "none"

    @property
    def is_loaded(self) -> bool:
        return self._source != "none"

    def get_pricing(self) -> dict[str, Any]:
        """Return current pricing info for trace logs."""
        return {
            "prompt_per_1m_usd": self._pricing.get("prompt_per_1m", 0.0),
            "completion_per_1m_usd": self._pricing.get("completion_per_1m", 0.0),
            "source": self._source,
        }

    async def fetch_openrouter(self, api_key: str, model: str) -> dict[str, Any]:
        """Fetch pricing for a specific model from OpenRouter.

        OpenRouter returns prices in USD per token in the fields:
          pricing.prompt   — input price per token
          pricing.completion — output price per token

        We convert to USD per 1M tokens for readability.
        """
        self._pricing = {"prompt_per_1m": 0.0, "completion_per_1m": 0.0}
        self._source = "none"
        self._raw_model_data = None

        if not model:
            return self.get_pricing()

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()

            models = data.get("data", [])
            for m in models:
                if m.get("id") == model:
                    self._raw_model_data = m
                    pricing = m.get("pricing", {})
                    prompt_per_token = float(pricing.get("prompt", "0") or "0")
                    completion_per_token = float(pricing.get("completion", "0") or "0")
                    self._pricing = {
                        "prompt_per_1m": prompt_per_token * 1_000_000,
                        "completion_per_1m": completion_per_token * 1_000_000,
                    }
                    self._source = "openrouter_api"
                    break

            if self._source == "none":
                self._source = "openrouter_model_not_found"

        except Exception:
            self._source = "openrouter_fetch_error"

        return self.get_pricing()

    def set_zero(self) -> None:
        """Set zero pricing for non-OpenRouter providers."""
        self._pricing = {"prompt_per_1m": 0.0, "completion_per_1m": 0.0}
        self._source = "not_openrouter"
        self._raw_model_data = None

    def calc_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int = 0,
    ) -> dict[str, float]:
        """Calculate cost breakdown in USD.

        Reasoning tokens are billed at the completion rate (standard for
        OpenRouter / OpenAI reasoning models).
        """
        p_per_1m = self._pricing.get("prompt_per_1m", 0.0)
        c_per_1m = self._pricing.get("completion_per_1m", 0.0)

        input_cost = prompt_tokens * p_per_1m / 1_000_000
        output_cost = completion_tokens * c_per_1m / 1_000_000
        reasoning_cost = reasoning_tokens * c_per_1m / 1_000_000

        return {
            "input_cost_usd": round(input_cost, 8),
            "output_cost_usd": round(output_cost, 8),
            "reasoning_cost_usd": round(reasoning_cost, 8),
            "total_cost_usd": round(input_cost + output_cost + reasoning_cost, 8),
        }

    def extract_usage(self, response_body: dict, is_openrouter: bool) -> dict[str, Any]:
        """Extract token usage from an API response body.

        For OpenRouter (OpenAI-compatible), the usage block is at:
          response["usage"]["prompt_tokens"]
          response["usage"]["completion_tokens"]
          response["usage"]["total_tokens"]

        Some reasoning models also include:
          response["usage"]["completion_tokens_details"]["reasoning_tokens"]
        or OpenRouter-specific:
          response["usage"]["native_tokens_reasoning"]

        Returns a normalized dict. If usage is unavailable, all values are 0.
        """
        usage_raw = response_body.get("usage") or {}
        prompt_tokens = int(usage_raw.get("prompt_tokens", 0))
        completion_tokens = int(usage_raw.get("completion_tokens", 0))
        total_tokens = int(usage_raw.get("total_tokens", 0))

        reasoning_tokens = 0
        if is_openrouter:
            reasoning_tokens = int(usage_raw.get("native_tokens_reasoning", 0))
            details = usage_raw.get("completion_tokens_details") or {}
            if not reasoning_tokens:
                reasoning_tokens = int(details.get("reasoning_tokens", 0))

        provider_cost = None
        if "total_cost" in usage_raw:
            try:
                provider_cost = float(usage_raw["total_cost"])
            except (ValueError, TypeError):
                pass
        if provider_cost is None and "total_cost" in response_body:
            try:
                provider_cost = float(response_body["total_cost"])
            except (ValueError, TypeError):
                pass

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": total_tokens or (prompt_tokens + completion_tokens),
            "provider_reported_cost_usd": provider_cost,
            "usage_raw": usage_raw if usage_raw else None,
        }
