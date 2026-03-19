"""Tests for notation_converter.py — bidirectional server ↔ Triumvirate."""
from __future__ import annotations

import pytest

from notation_converter import (
    convert_board,
    convert_legal_moves,
    convert_legal_moves_back,
    convert_move_back,
    to_server,
    to_triumvirate,
)


# ── Happy path: known cell pairs ─────────────────────────────────────────────

@pytest.mark.parametrize("server,tri", [
    ("A1", "W3/B3.0"),
    ("A2", "W3/B2.0"),
    ("A3", "W3/B1.0"),
    ("A4", "W3/B0.0"),
    ("D1", "W3/B3.3"),
    ("D4", "C/W.B"),
    ("E4", "C/W.R"),
    ("H1", "W3/R3.0"),
    ("A8", "B3/R3.0"),
    ("I5", "C/B.W"),
    ("L12", "R3/B3.0"),
    ("H12", "R3/W3.0"),
])
def test_to_triumvirate_known_cells(server, tri):
    assert to_triumvirate(server) == tri


@pytest.mark.parametrize("server,tri", [
    ("A1", "W3/B3.0"),
    ("D4", "C/W.B"),
    ("E4", "C/W.R"),
    ("A8", "B3/R3.0"),
    ("L12", "R3/B3.0"),
])
def test_to_server_known_cells(server, tri):
    assert to_server(tri) == server


def test_convert_legal_moves_simple():
    legal = {"A2": ["A3", "A4"]}
    result = convert_legal_moves(legal)
    assert to_triumvirate("A2") in result
    assert to_triumvirate("A3") in result[to_triumvirate("A2")]
    assert to_triumvirate("A4") in result[to_triumvirate("A2")]


def test_convert_legal_moves_back_simple():
    legal = {"A2": ["A3", "A4"]}
    tri = convert_legal_moves(legal)
    back = convert_legal_moves_back(tri)
    assert back == legal


def test_convert_board_adds_tri_notation():
    board = [{"notation": "A1", "color": "white", "type": "rook", "owner": "white"}]
    result = convert_board(board)
    assert result[0]["tri_notation"] == "W3/B3.0"


def test_convert_move_back():
    tri_from = to_triumvirate("A2")
    tri_to = to_triumvirate("A4")
    assert convert_move_back(tri_from, tri_to) == ("A2", "A4")


# ── Edge cases ───────────────────────────────────────────────────────────────

def test_to_triumvirate_center_cells_both():
    d4 = to_triumvirate("D4")
    e4 = to_triumvirate("E4")
    assert d4 == "C/W.B"
    assert e4 == "C/W.R"
    assert d4 != e4


def test_to_triumvirate_case_insensitive():
    assert to_triumvirate("a1") == to_triumvirate("A1")


def test_to_triumvirate_whitespace():
    assert to_triumvirate(" A1 ") == to_triumvirate("A1")


def test_convert_board_empty_list():
    assert convert_board([]) == []


def test_convert_legal_moves_empty():
    assert convert_legal_moves({}) == {}


def test_convert_board_does_not_mutate_original():
    original = [{"notation": "A1", "color": "white", "type": "rook", "owner": "white"}]
    convert_board(original)
    assert "tri_notation" not in original[0]


def test_convert_board_piece_without_notation():
    board = [{"color": "white", "type": "pawn", "owner": "white"}]
    result = convert_board(board)
    assert "tri_notation" not in result[0]


# ── Error paths ──────────────────────────────────────────────────────────────

def test_to_triumvirate_invalid_raises_keyerror():
    with pytest.raises(KeyError):
        to_triumvirate("Z99")


def test_to_server_invalid_raises_keyerror():
    with pytest.raises(KeyError):
        to_server("X1/Y2.3")


def test_convert_board_invalid_notation_keeps_original():
    board = [{"notation": "Z99", "color": "white", "type": "pawn", "owner": "white"}]
    result = convert_board(board)
    assert result[0]["tri_notation"] == "Z99"
