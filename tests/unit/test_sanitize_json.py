"""Tests for move_parser._sanitize_json_string — JSON cleanup for LLM output."""
from __future__ import annotations

import json

from move_parser import _sanitize_json_string


def test_sanitize_strips_markdown_fences():
    raw = '```json\n{"move_from": "A2", "move_to": "A4"}\n```'
    result = _sanitize_json_string(raw)
    assert json.loads(result) == {"move_from": "A2", "move_to": "A4"}


def test_sanitize_strips_markdown_fences_no_lang_tag():
    raw = '```\n{"move_from": "A2", "move_to": "A4"}\n```'
    result = _sanitize_json_string(raw)
    assert json.loads(result) == {"move_from": "A2", "move_to": "A4"}


def test_sanitize_escapes_control_chars():
    raw = '{"key": "val\x00ue"}'
    result = _sanitize_json_string(raw)
    parsed = json.loads(result)
    assert parsed["key"] == "val\u0000ue"


def test_sanitize_escapes_newlines_in_strings():
    raw = '{"key": "line1\nline2"}'
    result = _sanitize_json_string(raw)
    parsed = json.loads(result)
    assert parsed["key"] == "line1\nline2"


def test_sanitize_escapes_tabs_in_strings():
    raw = '{"key": "col1\tcol2"}'
    result = _sanitize_json_string(raw)
    parsed = json.loads(result)
    assert parsed["key"] == "col1\tcol2"


def test_sanitize_escapes_carriage_return():
    raw = '{"key": "a\rb"}'
    result = _sanitize_json_string(raw)
    parsed = json.loads(result)
    assert parsed["key"] == "a\rb"


def test_sanitize_handles_escaped_quotes():
    raw = r'{"key": "he said \"hello\""}'
    result = _sanitize_json_string(raw)
    parsed = json.loads(result)
    assert 'hello' in parsed["key"]


def test_sanitize_empty_string():
    assert _sanitize_json_string("") == ""


def test_sanitize_valid_json_unchanged():
    raw = '{"move_from": "E2", "move_to": "E4"}'
    assert _sanitize_json_string(raw) == raw


def test_sanitize_no_newline_outside_strings():
    raw = '{\n  "key": "val"\n}'
    result = _sanitize_json_string(raw)
    assert "\n" in result  # newlines outside strings are preserved
    assert json.loads(result) == {"key": "val"}
