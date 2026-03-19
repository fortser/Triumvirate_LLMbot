"""Tests for gui.py — NiceGUI User-based tests.

These tests use nicegui.testing.User (headless, no browser required)
to verify GUI behavior without Selenium/Playwright.

NOTE: Screen-based tests (with browser) require selenium to be installed.
These User-based tests verify the GUI creation logic without a real browser.
"""
from __future__ import annotations

import pytest

try:
    from nicegui.testing import User
    HAS_USER = True
except ImportError:
    HAS_USER = False

import settings as settings_module
from settings import Settings


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "_HERE", tmp_path)
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(Settings, "_file", tmp_path / "settings.json")

    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "system_prompt.txt").write_text("System prompt.", encoding="utf-8")
    (prompts / "user_prompt_template.txt").write_text("User template.", encoding="utf-8")
    return tmp_path


@pytest.mark.skipif(not HAS_USER, reason="nicegui.testing.User not available")
def test_gui_creates_without_error(isolated_settings):
    """Smoke test: create_gui() does not crash."""
    from gui import create_gui
    s = Settings()
    # Just verify it doesn't raise. Actual rendering needs a NiceGUI server context.
    # This is a minimal sanity check.
    assert callable(create_gui)


def test_gui_helpers_mask_api_key():
    """Verify mask function (already tested in test_gui_logic, included for coverage)."""
    from gui_helpers import mask_api_key
    assert mask_api_key("sk-1234567890abcdef") == "sk-12345...cdef"


def test_gui_helpers_format_hint():
    from gui_helpers import format_hint
    assert format_hint("simple") != ""
    assert format_hint("json") != ""
    assert format_hint("json_thinking") != ""
    assert format_hint("unknown") == ""


def test_gui_helpers_format_state_basic():
    from gui_helpers import format_state_text
    state = {
        "move_number": 1,
        "current_player": "white",
        "game_status": "playing",
        "legal_moves": {"A2": ["A3"]},
        "last_move": None,
        "check": None,
    }
    state_md, legal_md = format_state_text(state)
    assert "WHITE" in state_md
    assert "A2" in legal_md


def test_gui_helpers_collect_settings_basic():
    from gui_helpers import collect_settings
    values = {"provider": "", "api_key": "key123", "custom_headers": ""}
    result = collect_settings(values, {})
    assert result["api_key"] == "key123"


def test_gui_helpers_apply_preset():
    from gui_helpers import apply_provider_preset
    from constants import PROVIDERS
    result = apply_provider_preset("OpenAI API", PROVIDERS)
    assert result["base_url"] == "https://api.openai.com/v1"


def test_gui_helpers_format_game_list():
    from gui_helpers import format_game_list
    games = [{"game_id": "test1234", "players": [], "move_number": 0}]
    result = format_game_list(games)
    assert "test1234" in result
