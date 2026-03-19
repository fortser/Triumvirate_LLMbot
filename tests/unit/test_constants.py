"""Tests for constants.py — providers, version, bot naming."""
from __future__ import annotations

import re

import pytest

from constants import PROVIDERS, PROVIDER_ENV_KEY, VERSION, _PROVIDER_SHORT, make_bot_name


# ── make_bot_name ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("provider,model,expected_prefix", [
    ("Ollama (локальный)", "llama3.2", "LLM_Ollama_"),
    ("OpenAI API", "gpt-4o-mini", "LLM_OpenAI_"),
    ("Anthropic (native)", "claude-haiku-4-5-20251001", "LLM_Anthropic_"),
    ("OpenRouter", "openai/gpt-4.1-nano", "LLM_OpenRouter_"),
    ("LM Studio", "qwen2.5-7b", "LLM_LMStudio_"),
    ("Кастомный URL", "my-model", "LLM_Custom_"),
])
def test_make_bot_name_standard(provider, model, expected_prefix):
    name = make_bot_name(provider, model)
    assert name.startswith(expected_prefix)
    assert model.replace(" ", "-") in name


def test_make_bot_name_truncation():
    long_model = "a" * 80
    name = make_bot_name("OpenAI API", long_model)
    assert len(name) <= 80


def test_make_bot_name_empty_model():
    name = make_bot_name("OpenAI API", "")
    assert name.endswith("_unknown")


def test_make_bot_name_unknown_provider():
    name = make_bot_name("Some Provider", "test-model")
    assert name.startswith("LLM_Some_")


def test_make_bot_name_spaces_in_model():
    name = make_bot_name("OpenAI API", "my model")
    assert "my-model" in name


@pytest.mark.parametrize("provider,model", [
    ("OpenRouter", "x" * 100),
    ("Кастомный URL", "very/long/model/name/that/exceeds/normal/lengths"),
    ("OpenAI API", " " * 70 + "model"),
])
def test_make_bot_name_never_exceeds_80(provider, model):
    assert len(make_bot_name(provider, model)) <= 80


# ── PROVIDERS structure ──────────────────────────────────────────────────────

def test_providers_dict_structure():
    required_keys = {"base_url", "api_key", "model", "compat", "response_format"}
    for name, info in PROVIDERS.items():
        missing = required_keys - set(info.keys())
        assert not missing, f"Provider '{name}' missing keys: {missing}"


# ── PROVIDER_ENV_KEY ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("provider", ["OpenAI API", "Anthropic (native)", "OpenRouter"])
def test_provider_env_key_known(provider):
    assert provider in PROVIDER_ENV_KEY
    assert PROVIDER_ENV_KEY[provider]  # non-empty


# ── _PROVIDER_SHORT covers all PROVIDERS ─────────────────────────────────────

def test_provider_short_covers_all():
    for key in PROVIDERS:
        assert key in _PROVIDER_SHORT, f"'{key}' not in _PROVIDER_SHORT"


# ── VERSION format ───────────────────────────────────────────────────────────

def test_version_format():
    assert re.match(r"\d+\.\d+\.\d+", VERSION)
