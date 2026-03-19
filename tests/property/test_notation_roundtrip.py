"""Property-based tests for notation_converter roundtrip guarantees."""
from __future__ import annotations

from notation_converter import (
    _SERVER_TO_TRI,
    _TRI_TO_SERVER,
    convert_legal_moves,
    convert_legal_moves_back,
    to_server,
    to_triumvirate,
)


def test_roundtrip_all_96_cells():
    for server in _SERVER_TO_TRI:
        assert to_server(to_triumvirate(server)) == server


def test_reverse_roundtrip_all_96():
    for tri in _TRI_TO_SERVER:
        assert to_triumvirate(to_server(tri)) == tri


def test_lookup_tables_bijective():
    assert len(_SERVER_TO_TRI) == 96
    assert len(_TRI_TO_SERVER) == 96
    assert set(_SERVER_TO_TRI.values()) == set(_TRI_TO_SERVER.keys())
    assert set(_TRI_TO_SERVER.values()) == set(_SERVER_TO_TRI.keys())


def test_convert_legal_moves_roundtrip():
    legal = {"A2": ["A3", "A4"], "B1": ["A3", "C3"]}
    tri = convert_legal_moves(legal)
    back = convert_legal_moves_back(tri)
    assert back == legal
