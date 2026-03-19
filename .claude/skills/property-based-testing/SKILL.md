---
name: property-based-testing
description: >
  Property-based testing with Hypothesis for Python. Use when writing
  tests for serialization, validation, pure functions, data transformations,
  or when PBT would provide stronger coverage than example-based tests.
  Triggers: "hypothesis", "property test", "invariant", "roundtrip",
  "idempotent", "fuzz", "свойство", "инвариант".
---

# Property-Based Testing Guide

## When to Invoke (Automatic Detection)

Invoke when you detect:

- **Serialization pairs**: to_triumvirate/to_server roundtrip
- **Parsers**: MoveParser JSON/text parsing, _sanitize_json_string
- **Normalization**: _strip_piece_prefix, _norm_promo
- **Validators**: _validate against legal moves
- **Data structures**: lookup tables (_SERVER_TO_TRI, _TRI_TO_SERVER)

## Property Catalog

| Property         | Formula                         | Example Use Case                        |
|-----------------|---------------------------------|-----------------------------------------|
| **Roundtrip**    | `decode(encode(x)) == x`       | to_server(to_triumvirate(sq)) == sq     |
| **Idempotence**  | `f(f(x)) == f(x)`              | _sanitize_json_string idempotence       |
| **Invariant**    | Property holds before/after     | 96 cells always mapped, no orphans      |
| **Commutativity**| `f(a, b) == f(b, a)`           | N/A for this project                    |
| **Oracle**       | `new_impl(x) == reference(x)`  | N/A for this project                    |
| **Easy to Verify**| Verify output property         | parsed move is always in legal_moves    |
| **No Exception** | No crash on valid input         | _sanitize_json_string never crashes     |

## Core Patterns for This Project

### Notation Converter Roundtrip (CRITICAL)

```python
from hypothesis import given, strategies as st

# All 96 valid server notations
VALID_SERVER_NOTATIONS = [f"{c}{r}" for c in "ABCDEFGHIJKL" for r in range(1, 13)
                          if not (c in "EFGH" and r in range(5, 9))]
# Actually, build from the real lookup table:
from notation_converter import _SERVER_TO_TRI

@given(st.sampled_from(list(_SERVER_TO_TRI.keys())))
def test_roundtrip_server_to_tri_and_back(server_sq):
    from notation_converter import to_triumvirate, to_server
    tri = to_triumvirate(server_sq)
    back = to_server(tri)
    assert back == server_sq
```

### JSON Sanitizer Fuzzing (CRITICAL)

```python
@given(st.text(min_size=0, max_size=500))
def test_sanitize_never_crashes(raw):
    from move_parser import _sanitize_json_string
    result = _sanitize_json_string(raw)
    assert isinstance(result, str)

@given(st.text(min_size=0, max_size=500))
def test_sanitize_idempotence(raw):
    from move_parser import _sanitize_json_string
    once = _sanitize_json_string(raw)
    twice = _sanitize_json_string(once)
    # Idempotence: sanitizing twice gives same result
    assert once == twice
```

### MoveParser — parsed move is always legal

```python
@given(st.text(min_size=1, max_size=300))
def test_parser_result_always_legal_or_none(text):
    from move_parser import MoveParser
    parser = MoveParser()
    legal = {"A2": ["A3", "A4"], "B1": ["C3"]}
    result = parser.parse(text, legal, "simple")
    if result is not None:
        f, t, promo = result
        assert f.upper() in {k.upper() for k in legal}
        assert t.upper() in {v.upper() for v in legal[f]}
```

### Cost Calculation — non-negative

```python
@given(
    st.integers(min_value=0, max_value=1_000_000),
    st.integers(min_value=0, max_value=1_000_000),
    st.integers(min_value=0, max_value=1_000_000),
)
def test_cost_always_non_negative(prompt_tok, compl_tok, reason_tok):
    from pricing import PricingManager
    pm = PricingManager()
    pm._pricing = {"prompt_per_1m": 2.5, "completion_per_1m": 10.0}
    cost = pm.calc_cost(prompt_tok, compl_tok, reason_tok)
    assert cost["total_cost_usd"] >= 0
    assert cost["input_cost_usd"] >= 0
    assert cost["output_cost_usd"] >= 0
    assert cost["reasoning_cost_usd"] >= 0
```

### CI Profiles

```python
from hypothesis import settings, Phase

settings.register_profile("ci", max_examples=500, deadline=None)
settings.register_profile("dev", max_examples=50)
settings.register_profile("debug", max_examples=10,
                          phases=[Phase.explicit, Phase.generate])
# Usage: pytest --hypothesis-profile=ci
```

## When NOT to Use
- gui.py (NiceGUI code)
- main.py (argparse entry point)
- Simple accessor methods (Settings.__getitem__)
- Tests requiring real HTTP (use respx example-based instead)
