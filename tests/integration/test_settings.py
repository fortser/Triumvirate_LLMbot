"""Tests for settings.py — JSON-backed settings, .env loading, virtual keys."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import settings as settings_module
from settings import Settings, _FALLBACK_SYSTEM, _FALLBACK_USER_TEMPLATE, _load_dotenv


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    """Create Settings isolated to tmp_path."""
    monkeypatch.setattr(settings_module, "_HERE", tmp_path)
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "settings.json")
    # Patch the class-level _file default
    monkeypatch.setattr(Settings, "_file", tmp_path / "settings.json")
    return tmp_path


# ── Settings lifecycle ───────────────────────────────────────────────────────

def test_settings_defaults(isolated_settings):
    s = Settings()
    assert s["server_url"] == "https://triumvirate4llm.com"
    assert s["temperature"] == 0.3
    assert s["max_retries"] == 3


def test_settings_save_load_roundtrip(isolated_settings):
    s = Settings()
    s["temperature"] = 0.7
    s["model"] = "test-model"
    s.save()

    s2 = Settings()
    assert s2["temperature"] == 0.7
    assert s2["model"] == "test-model"


def test_settings_save_excludes_legacy_keys(isolated_settings):
    s = Settings()
    s.save()
    raw = json.loads(s._file.read_text(encoding="utf-8"))
    assert "system_prompt" not in raw
    assert "user_template" not in raw


# ── Virtual keys (prompt reading from files) ─────────────────────────────────

def test_settings_system_prompt_reads_file(isolated_settings, tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system_prompt.txt").write_text("Custom system prompt", encoding="utf-8")

    s = Settings()
    assert s["system_prompt"] == "Custom system prompt"


def test_settings_user_template_reads_file(isolated_settings, tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "user_prompt_template.txt").write_text("Custom template", encoding="utf-8")

    s = Settings()
    assert s["user_template"] == "Custom template"


def test_settings_system_prompt_fallback_when_missing(isolated_settings):
    s = Settings()
    assert s["system_prompt"] == _FALLBACK_SYSTEM


def test_settings_system_prompt_fallback_when_empty(isolated_settings, tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system_prompt.txt").write_text("", encoding="utf-8")

    s = Settings()
    assert s["system_prompt"] == _FALLBACK_SYSTEM


# ── API key resolution ───────────────────────────────────────────────────────

def test_settings_api_key_from_json(isolated_settings):
    s = Settings()
    s._d["api_key"] = "sk-test123"
    assert s["api_key"] == "sk-test123"


def test_settings_api_key_from_env(isolated_settings, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    s = Settings()
    s._d["api_key"] = ""
    s._d["provider"] = "OpenAI API"
    assert s["api_key"] == "sk-from-env"


def test_settings_api_key_no_env_mapping(isolated_settings):
    s = Settings()
    s._d["api_key"] = ""
    s._d["provider"] = "Ollama (локальный)"
    assert s["api_key"] == ""


# ── Setter blocking ─────────────────────────────────────────────────────────

def test_settings_legacy_key_write_ignored(isolated_settings):
    s = Settings()
    s["system_prompt"] = "should be ignored"
    # The internal dict should NOT have system_prompt
    assert "system_prompt" not in s._d


# ── Migration ────────────────────────────────────────────────────────────────

def test_settings_migrates_legacy_system_prompt(isolated_settings, tmp_path):
    config = {
        "system_prompt": "legacy system text",
        "model": "test",
    }
    (tmp_path / "settings.json").write_text(json.dumps(config), encoding="utf-8")

    s = Settings()
    # Prompt file should have been created
    prompt_file = tmp_path / "prompts" / "system_prompt.txt"
    assert prompt_file.exists()
    assert prompt_file.read_text(encoding="utf-8") == "legacy system text"


def test_settings_migrates_legacy_user_template(isolated_settings, tmp_path):
    config = {
        "user_template": "legacy template text",
        "model": "test",
    }
    (tmp_path / "settings.json").write_text(json.dumps(config), encoding="utf-8")

    s = Settings()
    prompt_file = tmp_path / "prompts" / "user_prompt_template.txt"
    assert prompt_file.exists()
    assert prompt_file.read_text(encoding="utf-8") == "legacy template text"


# ── Response format ──────────────────────────────────────────────────────────

def test_response_format_from_file(isolated_settings, tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "format_json.txt").write_text("Custom JSON format", encoding="utf-8")

    from settings import get_response_format
    assert get_response_format("json") == "Custom JSON format"


def test_response_format_fallback_known(isolated_settings):
    from settings import get_response_format, DEFAULT_RESPONSE_FORMAT
    assert get_response_format("simple") == DEFAULT_RESPONSE_FORMAT["simple"]


def test_response_format_fallback_unknown(isolated_settings):
    from settings import get_response_format, DEFAULT_RESPONSE_FORMAT
    assert get_response_format("unknown_format") == DEFAULT_RESPONSE_FORMAT["json_thinking"]


# ── .env loading ─────────────────────────────────────────────────────────────

def test_dotenv_sets_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_VAR_ABC=hello123\n", encoding="utf-8")
    monkeypatch.delenv("TEST_VAR_ABC", raising=False)
    _load_dotenv(env_file)
    assert os.environ.get("TEST_VAR_ABC") == "hello123"
    monkeypatch.delenv("TEST_VAR_ABC", raising=False)


def test_dotenv_doesnt_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_VAR_DEF", "original")
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_VAR_DEF=new_value\n", encoding="utf-8")
    _load_dotenv(env_file)
    assert os.environ["TEST_VAR_DEF"] == "original"


def test_dotenv_ignores_comments(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nTEST_VAR_GHI=val\n", encoding="utf-8")
    monkeypatch.delenv("TEST_VAR_GHI", raising=False)
    _load_dotenv(env_file)
    assert os.environ.get("TEST_VAR_GHI") == "val"
    monkeypatch.delenv("TEST_VAR_GHI", raising=False)


def test_dotenv_strips_quotes(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('TEST_VAR_JKL="quoted_val"\n', encoding="utf-8")
    monkeypatch.delenv("TEST_VAR_JKL", raising=False)
    _load_dotenv(env_file)
    assert os.environ.get("TEST_VAR_JKL") == "quoted_val"
    monkeypatch.delenv("TEST_VAR_JKL", raising=False)


def test_dotenv_nonexistent_file(tmp_path):
    _load_dotenv(tmp_path / "nonexistent.env")  # should not raise


# ── Properties ───────────────────────────────────────────────────────────────

def test_system_prompt_path_is_absolute(isolated_settings):
    s = Settings()
    assert s.system_prompt_path.is_absolute()


def test_user_template_path_is_absolute(isolated_settings):
    s = Settings()
    assert s.user_template_path.is_absolute()
