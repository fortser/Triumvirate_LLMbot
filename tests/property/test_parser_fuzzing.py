"""Property-based fuzz tests for MoveParser."""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from move_parser import MoveParser

parser = MoveParser()
LEGAL = {"A2": ["A3", "A4"], "B1": ["A3", "C3"]}


@given(text=st.text(min_size=0, max_size=500))
@settings(max_examples=200)
def test_parse_never_crashes_on_arbitrary_text(text):
    for fmt in ("simple", "json", "json_thinking"):
        result = parser.parse(text, LEGAL, fmt)
        # Should return None or a valid tuple, never crash
        assert result is None or (isinstance(result, tuple) and len(result) == 3)


@given(text=st.text(min_size=0, max_size=500))
@settings(max_examples=200)
def test_parse_result_always_in_legal(text):
    for fmt in ("simple", "json", "json_thinking"):
        result = parser.parse(text, LEGAL, fmt)
        if result is not None:
            f, t, _ = result
            legal_up = {k.upper(): [v.upper() for v in vs] for k, vs in LEGAL.items()}
            assert f in legal_up
            assert t in legal_up[f]
