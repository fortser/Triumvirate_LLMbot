"""Константы проекта: провайдеры, ключи окружения, версия, именование ботов.

Это leaf-модуль без зависимостей. От него зависят settings.py, bot_runner.py, gui.py.
"""
from __future__ import annotations

# ─── Version ──────────────────────────────────────────────────────────────────
VERSION = "2.2.0"

# ─── Provider presets ─────────────────────────────────────────────────────────
PROVIDERS: dict[str, dict] = {
    "Ollama (локальный)": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "llama3.2",
        "compat": True,
        "response_format": "simple",
    },
    "OpenAI API": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "compat": True,
        "response_format": "json_thinking",
    },
    "Anthropic (native)": {
        "base_url": "https://api.anthropic.com",
        "api_key": "",
        "model": "claude-haiku-4-5-20251001",
        "compat": False,
        "response_format": "json_thinking",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "model": "openai/gpt-4.1-nano",
        "compat": True,
        "temperature": 0.5,
        "max_tokens": 4096,
        "response_format": "json_thinking",
        "custom_headers": {
            "HTTP-Referer": "https://triumvirate4llm.com",
            "X-Title": "Three-Player Chess Bot",
        },
    },
    "LM Studio": {
        "base_url": "http://localhost:1234/v1",
        "api_key": "lm-studio",
        "model": "",
        "compat": True,
        "response_format": "simple",
    },
    "Кастомный URL": {
        "base_url": "http://localhost:8000/v1",
        "api_key": "",
        "model": "",
        "compat": True,
        "response_format": "json",
    },
}

# ─── Environment variable names for API keys ─────────────────────────────────
PROVIDER_ENV_KEY: dict[str, str] = {
    "OpenAI API":         "OPENAI_API_KEY",
    "Anthropic (native)": "ANTHROPIC_API_KEY",
    "OpenRouter":         "OPENROUTER_API_KEY",
}

# ─── Provider short names for bot naming ──────────────────────────────────────
_PROVIDER_SHORT: dict[str, str] = {
    "Ollama (локальный)": "Ollama",
    "OpenAI API":         "OpenAI",
    "Anthropic (native)": "Anthropic",
    "OpenRouter":         "OpenRouter",
    "LM Studio":          "LMStudio",
    "Кастомный URL":      "Custom",
}


def make_bot_name(provider: str, model: str) -> str:
    """Build a dynamic bot name from provider and model.

    Examples:
        LLM_OpenRouter_openai/gpt-4.1-nano
        LLM_LMStudio_qwen2.5-7b-instruct
        LLM_Anthropic_claude-haiku-4-5-20251001
    """
    prov_short = _PROVIDER_SHORT.get(provider, provider.split()[0])
    model_clean = model.strip() if model else "unknown"
    model_clean = model_clean.replace(" ", "-")
    name = f"LLM_{prov_short}_{model_clean}"
    if len(name) > 80:
        name = name[:80]
    return name
