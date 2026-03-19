"""Property-based fuzz tests for _sanitize_json_string."""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from move_parser import _sanitize_json_string


@given(text=st.text(min_size=0, max_size=500))
@settings(max_examples=200)
def test_sanitize_never_crashes(text):
    result = _sanitize_json_string(text)
    assert isinstance(result, str)


@given(text=st.text(min_size=0, max_size=300))
@settings(max_examples=200)
def test_sanitize_idempotent(text):
    once = _sanitize_json_string(text)
    twice = _sanitize_json_string(once)
    assert twice == once
