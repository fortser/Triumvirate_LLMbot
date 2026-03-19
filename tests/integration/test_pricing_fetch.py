"""Tests for pricing.PricingManager.fetch_openrouter and extract_usage."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from pricing import PricingManager


# ── fetch_openrouter ─────────────────────────────────────────────────────────

@respx.mock
async def test_fetch_success_converts_to_per_1m():
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=Response(200, json={
            "data": [{
                "id": "openai/gpt-4o",
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            }],
        })
    )
    pm = PricingManager()
    result = await pm.fetch_openrouter("key", "openai/gpt-4o")
    assert result["prompt_per_1m_usd"] == pytest.approx(3.0)
    assert result["completion_per_1m_usd"] == pytest.approx(15.0)
    assert pm._source == "openrouter_api"


@respx.mock
async def test_fetch_model_not_found():
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=Response(200, json={"data": []})
    )
    pm = PricingManager()
    await pm.fetch_openrouter("key", "nonexistent/model")
    assert pm._source == "openrouter_model_not_found"


@respx.mock
async def test_fetch_network_error():
    respx.get("https://openrouter.ai/api/v1/models").mock(side_effect=Exception("timeout"))
    pm = PricingManager()
    await pm.fetch_openrouter("key", "some-model")
    assert pm._source == "openrouter_fetch_error"


async def test_fetch_empty_model():
    pm = PricingManager()
    result = await pm.fetch_openrouter("key", "")
    assert result["prompt_per_1m_usd"] == 0.0
    assert pm._source == "none"


# ── extract_usage ────────────────────────────────────────────────────────────

def test_extract_usage_openai_format():
    pm = PricingManager()
    body = {"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
    u = pm.extract_usage(body, is_openrouter=False)
    assert u["prompt_tokens"] == 100
    assert u["completion_tokens"] == 50
    assert u["total_tokens"] == 150
    assert u["reasoning_tokens"] == 0


def test_extract_usage_native_reasoning_openrouter():
    pm = PricingManager()
    body = {"usage": {
        "prompt_tokens": 100, "completion_tokens": 50,
        "total_tokens": 150, "native_tokens_reasoning": 30,
    }}
    u = pm.extract_usage(body, is_openrouter=True)
    assert u["reasoning_tokens"] == 30


def test_extract_usage_completion_details_reasoning():
    pm = PricingManager()
    body = {"usage": {
        "prompt_tokens": 100, "completion_tokens": 50,
        "total_tokens": 150,
        "completion_tokens_details": {"reasoning_tokens": 20},
    }}
    u = pm.extract_usage(body, is_openrouter=True)
    assert u["reasoning_tokens"] == 20


def test_extract_usage_reasoning_ignored_non_openrouter():
    pm = PricingManager()
    body = {"usage": {
        "prompt_tokens": 100, "completion_tokens": 50,
        "total_tokens": 150, "native_tokens_reasoning": 30,
    }}
    u = pm.extract_usage(body, is_openrouter=False)
    assert u["reasoning_tokens"] == 0


def test_extract_usage_provider_cost_in_usage():
    pm = PricingManager()
    body = {"usage": {
        "prompt_tokens": 10, "completion_tokens": 5,
        "total_tokens": 15, "total_cost": 0.001,
    }}
    u = pm.extract_usage(body, is_openrouter=True)
    assert u["provider_reported_cost_usd"] == pytest.approx(0.001)


def test_extract_usage_provider_cost_top_level():
    pm = PricingManager()
    body = {
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "total_cost": 0.002,
    }
    u = pm.extract_usage(body, is_openrouter=True)
    assert u["provider_reported_cost_usd"] == pytest.approx(0.002)


def test_extract_usage_empty():
    pm = PricingManager()
    u = pm.extract_usage({}, is_openrouter=False)
    assert u["prompt_tokens"] == 0
    assert u["total_tokens"] == 0
    assert u["provider_reported_cost_usd"] is None


def test_extract_usage_total_tokens_fallback():
    pm = PricingManager()
    body = {"usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    u = pm.extract_usage(body, is_openrouter=False)
    assert u["total_tokens"] == 150  # fallback: prompt + completion
