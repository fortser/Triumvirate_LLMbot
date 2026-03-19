"""Shared fixtures for the Triumvirate LLM Bot test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to sys.path so flat imports (constants, settings, etc.) work.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ── Sample data fixtures ────────────────────────────────────────────────────

@pytest.fixture()
def sample_legal_moves():
    return {"A2": ["A3", "A4"], "B2": ["B3"]}


@pytest.fixture()
def sample_state(sample_legal_moves):
    return {
        "move_number": 5,
        "current_player": "white",
        "game_status": "playing",
        "legal_moves": sample_legal_moves,
        "board": [
            {"notation": "A2", "color": "white", "type": "pawn", "owner": "white"},
            {"notation": "E8", "color": "black", "type": "king", "owner": "black"},
        ],
        "players": [
            {"color": "white", "status": "active"},
            {"color": "black", "status": "active"},
            {"color": "red", "status": "active"},
        ],
        "last_move": {
            "from_square": "E7",
            "to_square": "E5",
            "move_type": "normal",
        },
        "check": None,
        "position_3pf": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR",
    }


@pytest.fixture()
def sample_board():
    return [
        {"notation": "A1", "color": "white", "type": "rook", "owner": "white"},
        {"notation": "B1", "color": "white", "type": "knight", "owner": "white"},
        {"notation": "E8", "color": "black", "type": "king", "owner": "black"},
    ]


@pytest.fixture()
def settings_factory(tmp_path, monkeypatch):
    """Create a Settings instance that reads/writes from tmp_path."""
    import settings as settings_module

    monkeypatch.setattr(settings_module, "_HERE", tmp_path)
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "settings.json")

    def _factory():
        s = settings_module.Settings()
        s._file = tmp_path / "settings.json"
        return s

    return _factory


@pytest.fixture()
def pricing_manager():
    from pricing import PricingManager
    return PricingManager()
