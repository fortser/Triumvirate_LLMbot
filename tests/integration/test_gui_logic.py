"""Tests for gui_helpers.py — extracted GUI business logic."""
from __future__ import annotations

import os

import pytest

from constants import PROVIDERS
from gui_helpers import (
    apply_provider_preset,
    collect_settings,
    format_game_list,
    format_hint,
    format_state_text,
    mask_api_key,
)


# ── format_state_text ────────────────────────────────────────────────────────

def _make_state(**overrides):
    base = {
        "move_number": 5,
        "current_player": "white",
        "game_status": "playing",
        "legal_moves": {"A2": ["A3", "A4"]},
        "board": [],
        "players": [],
        "last_move": {"from_square": "E7", "to_square": "E5"},
        "check": None,
    }
    base.update(overrides)
    return base


def test_format_state_basic():
    state_md, legal_md = format_state_text(_make_state())
    assert "WHITE" in state_md
    assert "#5" in state_md


def test_format_state_check():
    state = _make_state(check={"is_check": True, "checked_colors": ["white"]})
    state_md, _ = format_state_text(state)
    assert "CHECK" in state_md


def test_format_state_last_move():
    state_md, _ = format_state_text(_make_state())
    assert "E7" in state_md
    assert "E5" in state_md


def test_format_state_no_last_move():
    state_md, _ = format_state_text(_make_state(last_move=None))
    assert "\u2014" in state_md  # em dash


def test_format_state_legal_moves():
    _, legal_md = format_state_text(_make_state())
    assert "A2" in legal_md
    assert "A3" in legal_md


def test_format_state_no_legal_moves():
    _, legal_md = format_state_text(_make_state(legal_moves={}))
    assert "\u043d\u0435\u0442" in legal_md  # "нет" in Russian


# ── format_game_list ─────────────────────────────────────────────────────────

def test_format_game_list_multiple():
    games = [
        {"game_id": "abc12345", "players": [
            {"color": "white", "name": "Bot1"},
            {"color": "black", "name": "Bot2"},
        ], "move_number": 10},
        {"game_id": "def67890", "players": [], "move_number": 0},
    ]
    result = format_game_list(games)
    assert "abc12345" in result
    assert "def67890" in result
    assert "Bot1" in result


def test_format_game_list_empty():
    result = format_game_list([])
    assert "\u043d\u0435\u0442" in result  # "нет"


# ── collect_settings ─────────────────────────────────────────────────────────

def test_collect_settings_custom_headers_json():
    values = {"custom_headers": '{"X-Key": "val"}', "provider": ""}
    result = collect_settings(values, {})
    assert result["custom_headers"] == {"X-Key": "val"}


def test_collect_settings_invalid_json():
    values = {"custom_headers": "{bad", "provider": ""}
    result = collect_settings(values, {})
    assert result["custom_headers"] == {}


def test_collect_settings_empty_headers():
    values = {"custom_headers": "", "provider": ""}
    result = collect_settings(values, {})
    assert result["custom_headers"] == {}


def test_collect_settings_env_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    values = {"api_key": "", "provider": "OpenAI API"}
    result = collect_settings(values, {"OpenAI API": "OPENAI_API_KEY"})
    assert result["api_key"] == "sk-env-key"


def test_collect_settings_strips_whitespace():
    values = {"server_url": "  https://example.com  ", "model": " gpt-4o ", "provider": ""}
    result = collect_settings(values, {})
    assert result["server_url"] == "https://example.com"
    assert result["model"] == "gpt-4o"


# ── apply_provider_preset ───────────────────────────────────────────────────

def test_apply_preset_openai():
    result = apply_provider_preset("OpenAI API", PROVIDERS)
    assert result["base_url"] == "https://api.openai.com/v1"
    assert result["model"] == "gpt-4o-mini"
    assert result["compat"] is True


def test_apply_preset_anthropic():
    result = apply_provider_preset("Anthropic (native)", PROVIDERS)
    assert result["compat"] is False
    assert "claude" in result["model"]


def test_apply_preset_openrouter():
    result = apply_provider_preset("OpenRouter", PROVIDERS)
    assert "openrouter" in result["base_url"]
    assert result["custom_headers"]  # non-empty JSON string


def test_apply_preset_ollama():
    result = apply_provider_preset("Ollama (локальный)", PROVIDERS)
    assert "localhost" in result["base_url"]


def test_apply_preset_unknown():
    result = apply_provider_preset("NonExistent", PROVIDERS)
    assert result == {}


# ── mask_api_key ─────────────────────────────────────────────────────────────

def test_mask_api_key_long():
    key = "sk-1234567890abcdef"
    result = mask_api_key(key)
    assert result.startswith("sk-12345")
    assert result.endswith("cdef")
    assert "..." in result


def test_mask_api_key_short():
    assert mask_api_key("short") == "***"


def test_mask_api_key_empty():
    assert mask_api_key("") == ""


# ── format_hint ──────────────────────────────────────────────────────────────

def test_format_hint_simple():
    assert "E2 E4" in format_hint("simple")


def test_format_hint_json():
    assert "from" in format_hint("json")


def test_format_hint_json_thinking():
    assert "thinking" in format_hint("json_thinking")
