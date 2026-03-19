---
name: pytest-patterns
description: >
  Production-grade pytest patterns: fixtures, parametrize, markers,
  conftest, async, coverage. Use when user mentions "pytest", "conftest",
  "@pytest.fixture", "@pytest.mark", "test", "coverage", "тест".
languages:
  - Python
category: unit-testing
---

# Pytest Patterns

## Project Test Structure

```
decomp/
├── tests/
│   ├── conftest.py          # Shared fixtures (Settings, game states, respx)
│   ├── unit/                # Pure functions: notation_converter, move_parser, constants, pricing.calc_cost
│   │   ├── test_notation_converter.py
│   │   ├── test_move_parser.py
│   │   ├── test_constants.py
│   │   ├── test_pricing_calc.py
│   │   └── test_sanitize_json.py
│   ├── integration/         # Multi-module with real deps + respx mocks for HTTP
│   │   ├── test_settings.py
│   │   ├── test_prompt_builder.py
│   │   ├── test_tracer.py
│   │   ├── test_llm_client.py
│   │   ├── test_arena_client.py
│   │   ├── test_pricing_fetch.py
│   │   └── test_bot_runner.py
│   └── property/            # Hypothesis-based
│       ├── test_notation_roundtrip.py
│       ├── test_parser_fuzzing.py
│       └── test_sanitize_json_fuzzing.py
├── pyproject.toml
```

## conftest.py for This Project

```python
import pytest
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """Isolated Settings with tmp_path storage, no side effects."""
    import settings as settings_mod
    monkeypatch.setattr(settings_mod, '_HERE', tmp_path)
    monkeypatch.setattr(settings_mod, 'SETTINGS_FILE', tmp_path / "test_settings.json")
    from settings import Settings
    Settings._file = tmp_path / "test_settings.json"
    s = Settings()
    return s


@pytest.fixture
def make_game_state():
    """Factory for minimal valid game state dicts."""
    def _make(
        current_player="white",
        move_number=1,
        legal_moves=None,
        game_status="playing",
        board=None,
        last_move=None,
        **kwargs,
    ):
        state = {
            "game_status": game_status,
            "current_player": current_player,
            "move_number": move_number,
            "legal_moves": legal_moves or {"A2": ["A3", "A4"]},
            "board": board or [],
            "last_move": last_move,
            "check": None,
            "position_3pf": "test-position",
            "players": [],
        }
        state.update(kwargs)
        return state
    return _make


@pytest.fixture
def sample_legal_moves():
    """Legal moves dict for testing (server notation)."""
    return {
        "A2": ["A3", "A4"],
        "B2": ["B3", "B4"],
        "C1": ["A3", "B3"],
        "E2": ["E3", "E4"],
    }


@pytest.fixture
def sample_legal_moves_tri():
    """Legal moves dict in Triumvirate notation."""
    return {
        "W3/B2.0": ["W3/B1.0", "W3/B0.0"],
        "W3/B2.1": ["W3/B1.1", "W3/B0.1"],
    }


@pytest.fixture
def tracer(tmp_path):
    """MoveTracer writing to tmp_path."""
    from tracer import MoveTracer
    return MoveTracer(tmp_path / "logs")


@pytest.fixture
def noop_callbacks():
    """No-op callback functions for BotRunner."""
    logs = []
    statuses = []
    states = []
    return {
        "on_log": lambda msg: logs.append(msg),
        "on_status": lambda msg: statuses.append(msg),
        "on_state": lambda state: states.append(state),
        "logs": logs,
        "statuses": statuses,
        "states": states,
    }
```

## Markers

```python
# Registration in pyproject.toml
@pytest.mark.slow           # Long tests (>5 sec)
@pytest.mark.integration    # Real dependencies (respx, tmp_path)
@pytest.mark.xfail(reason="Known bug #N")  # Known bugs
```

## Quick Reference

| Task                    | Command                                         |
|-------------------------|-------------------------------------------------|
| Run all                 | `pytest`                                        |
| Unit only               | `pytest tests/unit/`                            |
| Integration only        | `pytest tests/integration/`                     |
| Property only           | `pytest tests/property/`                        |
| Stop on first fail      | `pytest -x`                                     |
| Re-run last failed      | `pytest --lf`                                   |
| Coverage                | `pytest --cov=. --cov-report=term-missing --cov-config=pyproject.toml` |
| Verbose + long TB       | `pytest -v --tb=long`                           |
| Single test             | `pytest tests/unit/test_move_parser.py::test_name` |
| By keyword              | `pytest -k "triumvirate and not slow"`          |
