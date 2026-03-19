"""Tests for move_parser.MoveParser — LLM response parsing and validation."""
from __future__ import annotations

import pytest

from move_parser import MoveParser, PROMO_MAP

parser = MoveParser()

LEGAL = {"A2": ["A3", "A4"], "B1": ["A3", "C3"], "E2": ["E3", "E4"]}


# ── JSON format ─────────────────────────────────────────────────────────────

def test_parser_extracts_move_from_standard_json():
    text = '{"move_from": "A2", "move_to": "A4"}'
    assert parser.parse(text, LEGAL, "json") == ("A2", "A4", None)


def test_parser_extracts_move_from_json_with_thinking():
    text = '{"thinking": "I should push the pawn", "move_from": "E2", "move_to": "E4"}'
    assert parser.parse(text, LEGAL, "json_thinking") == ("E2", "E4", None)


def test_parser_extracts_move_from_legacy_keys():
    text = '{"from": "A2", "to": "A3"}'
    assert parser.parse(text, LEGAL, "json") == ("A2", "A3", None)


def test_parser_extracts_promotion_from_json():
    legal = {"A7": ["A8"]}
    text = '{"move_from": "A7", "move_to": "A8", "promotion": "queen"}'
    assert parser.parse(text, legal, "json") == ("A7", "A8", "queen")


def test_parser_handles_markdown_fences_json():
    text = '```json\n{"move_from": "A2", "move_to": "A4"}\n```'
    assert parser.parse(text, LEGAL, "json") == ("A2", "A4", None)


# ── Simple format ────────────────────────────────────────────────────────────

def test_parser_extracts_move_from_simple_two_coords():
    assert parser.parse("A2 A4", LEGAL, "simple") == ("A2", "A4", None)


def test_parser_extracts_promotion_from_simple():
    legal = {"A7": ["A8"]}
    assert parser.parse("A7 A8 =Q", legal, "simple") == ("A7", "A8", "queen")


def test_parser_extracts_coords_in_text():
    text = "I recommend moving from A2 to A4 for better control."
    assert parser.parse(text, LEGAL, "simple") == ("A2", "A4", None)


def test_parser_skips_illegal_simple():
    text = "A2 B5 A2 A3"
    result = parser.parse(text, LEGAL, "simple")
    assert result == ("A2", "A3", None)


# ── Triumvirate notation ────────────────────────────────────────────────────

def test_parser_extracts_tri_json():
    tri_legal = {"W3/B2.0": ["W3/B1.0", "W3/B0.0"]}
    text = '{"move_from": "W3/B2.0", "move_to": "W3/B0.0"}'
    assert parser.parse(text, tri_legal, "json", triumvirate=True) == (
        "W3/B2.0", "W3/B0.0", None
    )


def test_parser_extracts_tri_simple():
    tri_legal = {"W3/B2.0": ["W3/B1.0", "W3/B0.0"]}
    text = "W3/B2.0 W3/B0.0"
    assert parser.parse(text, tri_legal, "simple", triumvirate=True) == (
        "W3/B2.0", "W3/B0.0", None
    )


# ── Piece prefix strip (server notation) ────────────────────────────────────

@pytest.mark.parametrize("prefix", ["N", "B", "R", "Q", "K", "P"])
def test_parser_strips_piece_prefix_server(prefix):
    text = f'{{"move_from": "{prefix}E2", "move_to": "E4"}}'
    assert parser.parse(text, LEGAL, "json") == ("E2", "E4", None)


# ── Piece prefix strip (Triumvirate) ────────────────────────────────────────

def test_parser_strips_tri_prefix_with_colon():
    tri_legal = {"W3/B2.0": ["W3/B1.0"]}
    text = '{"move_from": "P:W3/B2.0", "move_to": "W3/B1.0"}'
    assert parser.parse(text, tri_legal, "json", triumvirate=True) == (
        "W3/B2.0", "W3/B1.0", None
    )


def test_parser_strips_tri_prefix_without_colon():
    tri_legal = {"W3/B2.0": ["W3/B1.0"]}
    text = '{"move_from": "PW3/B2.0", "move_to": "W3/B1.0"}'
    assert parser.parse(text, tri_legal, "json", triumvirate=True) == (
        "W3/B2.0", "W3/B1.0", None
    )


def test_parser_tri_prefix_ambiguous_wbr_not_stripped():
    """W, B, R are sector letters, not piece prefixes — must NOT be stripped."""
    tri_legal = {"W3/B2.0": ["W3/B1.0"]}
    text = '{"move_from": "W3/B2.0", "move_to": "W3/B1.0"}'
    assert parser.parse(text, tri_legal, "json", triumvirate=True) is not None


# ── Edge cases ───────────────────────────────────────────────────────────────

def test_parser_no_braces_returns_none():
    assert parser.parse("just some text", LEGAL, "json") is None


def test_parser_invalid_json_returns_none():
    assert parser.parse("{move_from: A2, move_to: A4", LEGAL, "json") is None


def test_parser_missing_keys_returns_none():
    text = '{"thinking": "let me think"}'
    assert parser.parse(text, LEGAL, "json") is None


def test_parser_illegal_move_returns_none():
    text = '{"move_from": "A2", "move_to": "A5"}'
    assert parser.parse(text, LEGAL, "json") is None


def test_parser_same_coords_skipped():
    text = "A2 A2 A2 A4"
    assert parser.parse(text, LEGAL, "simple") == ("A2", "A4", None)


def test_parser_empty_text_returns_none():
    assert parser.parse("", LEGAL, "json") is None
    assert parser.parse("", LEGAL, "simple") is None


def test_parser_case_insensitive():
    text = '{"move_from": "a2", "move_to": "a4"}'
    assert parser.parse(text, LEGAL, "json") == ("A2", "A4", None)


# ── Promotion normalization ──────────────────────────────────────────────────

def test_promotion_standard_names():
    p = parser._norm_promo
    assert p("queen") == "queen"
    assert p("rook") == "rook"
    assert p("bishop") == "bishop"
    assert p("knight") == "knight"


def test_promotion_single_letter():
    p = parser._norm_promo
    assert p("q") == "queen"
    assert p("r") == "rook"
    assert p("b") == "bishop"
    assert p("n") == "knight"


def test_promotion_triumvirate_names():
    p = parser._norm_promo
    assert p("marshal") == "queen"
    assert p("train") == "rook"
    assert p("drone") == "bishop"
    assert p("noctis") == "knight"


def test_promotion_none_and_unknown():
    assert parser._norm_promo(None) is None
    assert parser._norm_promo("xyz") is None
