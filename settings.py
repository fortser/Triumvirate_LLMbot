"""Персистентные настройки приложения (JSON-backed) и дефолтные промпты.

Зависимости: constants (только VERSION неявно, через DEFAULTS).
Зависимые: bot_runner, gui, main.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
SETTINGS_FILE = _HERE / "llm_bot_gui_settings_v2.json"
_PROMPTS_DIR = _HERE / "prompts"


# ─── Prompt file reader ──────────────────────────────────────────────────────
def _read_prompt(filename: str, fallback: str) -> str:
    p = _PROMPTS_DIR / filename
    if p.exists():
        return p.read_text(encoding="utf-8")
    return fallback


# ─── Default prompts ─────────────────────────────────────────────────────────
DEFAULT_SYSTEM = _read_prompt(
    "system_prompt.txt",
    "You are a chess engine playing Three-Player Chess on a 96-cell hexagonal board.\n"
    "Columns A–L, rows 1–12. Three players: White, Black, Red.\n"
    "Turn order: White → Black → Red.\n"
    "Analyze the position carefully. Prioritize king safety, material, center control.",
)

DEFAULT_USER_TEMPLATE = _read_prompt(
    "user_prompt_template.txt",
    "Move #{{move_number}} | You are {{current_player}}\n\n"
    "Position (3PF): {{position_3pf}}\n\n"
    "Board:\n{{board}}\n\n"
    "Legal moves:\n{{legal_moves}}\n\n"
    "Last move: {{last_move}}\n"
    "{{check}}",
)

DEFAULT_RESPONSE_FORMAT: dict[str, str] = {
    "simple": (
        "Reply with EXACTLY one line: FROM TO\n"
        "Example: E2 E4\n"
        "For promotion: E7 E8 =Q\n"
        "Valid promotion pieces: Q R B N\n"
        "ONLY use moves from the legal moves list provided."
    ),
    "json": (
        "Respond with a JSON object only (no markdown, no explanation):\n"
        '{"from": "E2", "to": "E4"}\n'
        'For promotion: {"from": "E7", "to": "E8", "promotion": "queen"}\n'
        "Promotion values: queen | rook | bishop | knight\n"
        "ONLY use moves from the legal moves list."
    ),
    "json_thinking": (
        "Respond with a JSON object only (no markdown):\n"
        '{"thinking": "your analysis", "from": "E2", "to": "E4"}\n'
        'For promotion: {"thinking": "...", "from": "E7", "to": "E8", "promotion": "queen"}\n'
        "Use the thinking field to reason step by step before deciding.\n"
        "ONLY use moves from the legal moves list."
    ),
}


# ─── Settings class ──────────────────────────────────────────────────────────
class Settings:
    """JSON-backed application settings."""

    _file: Path = SETTINGS_FILE

    DEFAULTS: dict[str, Any] = {
        "server_url": "https://triumvirate4llm.com",
        "bot_name": "",
        "auto_bot_name": True,
        "provider": "OpenAI API",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "compat": True,
        "custom_headers": {},
        "temperature": 0.3,
        "max_tokens": 300,
        "response_format": "json_thinking",
        "system_prompt": DEFAULT_SYSTEM,
        "user_template": DEFAULT_USER_TEMPLATE,
        "additional_rules": "",
        "max_retries": 3,
        "poll_interval": 0.5,
        "auto_skip_waiting": False,
        "fallback_random": True,
    }

    def __init__(self) -> None:
        self._d: dict[str, Any] = dict(self.DEFAULTS)
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                stored = json.loads(self._file.read_text(encoding="utf-8"))
                self._d.update(stored)
            except Exception:
                pass

    def save(self) -> None:
        try:
            self._file.write_text(
                json.dumps(self._d, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self._d.get(key, self.DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self._d[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)
