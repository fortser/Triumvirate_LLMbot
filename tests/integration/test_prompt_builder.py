"""Tests for prompt_builder.py — prompt assembly from settings + game state."""
from __future__ import annotations

import json

import pytest

import settings as settings_module
from prompt_builder import PromptBuilder
from settings import Settings


@pytest.fixture()
def builder():
    return PromptBuilder()


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "_HERE", tmp_path)
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(Settings, "_file", tmp_path / "settings.json")

    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "system_prompt.txt").write_text(
        "You are a chess engine.", encoding="utf-8"
    )
    (prompts / "user_prompt_template.txt").write_text(
        "Move #{{move_number}} | You are {{current_player}}\n"
        "Legal: {{legal_moves}}\nLast: {{last_move}}\n{{check}}\nBoard:\n{{board}}",
        encoding="utf-8",
    )
    (prompts / "format_json_thinking.txt").write_text(
        "Respond with JSON.", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def state():
    return {
        "move_number": 10,
        "current_player": "white",
        "game_status": "playing",
        "legal_moves": {"A2": ["A3", "A4"]},
        "board": [
            {"notation": "A2", "color": "white", "type": "pawn", "owner": "white"},
        ],
        "players": [
            {"color": "white", "status": "active"},
        ],
        "last_move": {"from_square": "E7", "to_square": "E5", "move_type": "normal"},
        "check": None,
        "position_3pf": "some-3pf",
    }


# ── Build basic ──────────────────────────────────────────────────────────────

def test_build_returns_system_and_user(builder, isolated_settings, state):
    s = Settings()
    msgs = builder.build(state, s)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


def test_build_includes_output_format(builder, isolated_settings, state):
    s = Settings()
    msgs = builder.build(state, s)
    assert "OUTPUT FORMAT" in msgs[0]["content"]


def test_build_includes_additional_rules(builder, isolated_settings, state):
    s = Settings()
    s._d["additional_rules"] = "Always protect the king"
    msgs = builder.build(state, s)
    assert "Always protect the king" in msgs[0]["content"]
    assert "ADDITIONAL RULES" in msgs[0]["content"]


# ── Game state rendering ────────────────────────────────────────────────────

def test_build_last_move_text(builder, isolated_settings, state):
    s = Settings()
    msgs = builder.build(state, s)
    assert "E7" in msgs[1]["content"]
    assert "E5" in msgs[1]["content"]


def test_build_last_move_with_type(builder, isolated_settings, state):
    state["last_move"]["move_type"] = "capture"
    s = Settings()
    msgs = builder.build(state, s)
    assert "capture" in msgs[1]["content"]


def test_build_last_move_none(builder, isolated_settings, state):
    state["last_move"] = None
    s = Settings()
    msgs = builder.build(state, s)
    assert "none (game start)" in msgs[1]["content"]


def test_build_check_from_check_field(builder, isolated_settings, state):
    state["check"] = {"is_check": True, "checked_colors": ["white"]}
    s = Settings()
    msgs = builder.build(state, s)
    assert "CHECK" in msgs[1]["content"]


def test_build_check_from_player_status(builder, isolated_settings, state):
    state["players"][0]["status"] = "in_check"
    s = Settings()
    msgs = builder.build(state, s)
    assert "CHECK" in msgs[1]["content"]


def test_build_no_check(builder, isolated_settings, state):
    s = Settings()
    msgs = builder.build(state, s)
    # No CHECK text should appear
    assert "CHECK" not in msgs[1]["content"]


# ── Triumvirate mode ────────────────────────────────────────────────────────

def test_build_with_tri_legal(builder, isolated_settings, state):
    s = Settings()
    tri_legal = {"W3/B2.0": ["W3/B1.0", "W3/B0.0"]}
    msgs = builder.build(state, s, tri_legal=tri_legal)
    assert "W3/B2.0" in msgs[1]["content"]


def test_build_with_tri_last_move(builder, isolated_settings, state):
    s = Settings()
    tri_legal = {"W3/B2.0": ["W3/B1.0"]}
    msgs = builder.build(
        state, s,
        tri_legal=tri_legal,
        tri_last_move=("W3/B3.0", "W3/B2.0"),
    )
    assert "W3/B3.0" in msgs[1]["content"]


def test_build_with_tri_board(builder, isolated_settings, state):
    s = Settings()
    tri_legal = {"W3/B2.0": ["W3/B1.0"]}
    tri_board = [
        {"notation": "A2", "tri_notation": "W3/B2.0",
         "color": "white", "type": "pawn", "owner": "white"},
    ]
    msgs = builder.build(state, s, tri_legal=tri_legal, tri_board=tri_board)
    assert "W3/B2.0" in msgs[1]["content"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def test_fmt_legal_empty(builder):
    assert builder._fmt_legal({}) == "(none)"


def test_fmt_legal_sorted(builder):
    legal = {"B2": ["B4", "B3"], "A2": ["A3"]}
    result = builder._fmt_legal(legal)
    lines = result.split("\n")
    assert lines[0].strip().startswith("A2")
    assert lines[1].strip().startswith("B2")


def test_fmt_board_grouped(builder):
    board = [
        {"notation": "A1", "color": "white", "type": "rook", "owner": "white"},
        {"notation": "E8", "color": "black", "type": "king", "owner": "black"},
    ]
    result = builder._fmt_board(board, "white")
    assert "WHITE" in result
    assert "BLACK" in result
    assert "YOU" in result


def test_fmt_board_captured(builder):
    board = [
        {"notation": "A1", "color": "white", "type": "rook", "owner": "black"},
    ]
    result = builder._fmt_board(board, "white")
    assert "(b)" in result


def test_fmt_board_tri_symbols(builder):
    tri_board = [
        {"notation": "A1", "tri_notation": "W3/B3.0",
         "color": "white", "type": "KING", "owner": "white"},
    ]
    result = builder._fmt_board_tri(tri_board, "white")
    assert "L:" in result  # KING -> L (Leader)


def test_fmt_board_empty(builder):
    assert builder._fmt_board([], "white") == ""
    assert builder._fmt_board_tri([], "white") == ""


def test_fill_template_double_braces(builder):
    tmpl = "Hello {{name}}!"
    assert builder._fill_template(tmpl, {"name": "World"}) == "Hello World!"


def test_fill_template_single_braces(builder):
    tmpl = "Hello {name}!"
    assert builder._fill_template(tmpl, {"name": "World"}) == "Hello World!"


def test_fill_template_missing_key(builder):
    tmpl = "Hello {{name}} and {{unknown}}!"
    result = builder._fill_template(tmpl, {"name": "World"})
    assert "World" in result
    assert "{{unknown}}" in result
