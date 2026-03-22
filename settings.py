"""Персистентные настройки приложения (JSON-backed) и дефолтные промпты.

Промпты хранятся в отдельных текстовых файлах (prompts/),
а в JSON-настройках — только пути к ним.

Зависимости: constants.py (PROVIDER_ENV_KEY).
Зависимые: bot_runner, gui, main, prompt_builder.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from constants import PROVIDER_ENV_KEY

# ─── .env loader (no external deps) ─────────────────────────────────────────
def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (if not already set)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)

# ─── Paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
SETTINGS_FILE = _HERE / "llm_bot_gui_settings_v2.json"
_PROMPTS_DIR = _HERE / "prompts"

# Load .env on module import
_load_dotenv(_HERE / ".env")

# ─── Built-in fallback prompts ───────────────────────────────────────────────
# Used ONLY when prompt files do not exist on disk (first launch / deleted).
_FALLBACK_SYSTEM = (
    "You are a chess engine playing Three-Player Chess on a 96-cell hexagonal board.\n"
    "Columns A–L, rows 1–12. Three players: White, Black, Red.\n"
    "Turn order: White → Black → Red.\n"
    "Analyze the position carefully. Prioritize Leader safety, material, center control."
)

_FALLBACK_USER_TEMPLATE = (
    "Move #{{move_number}} | You are {{current_player}}\n\n"
    "Board:\n{{board}}\n\n"
    "Legal moves:\n{{legal_moves}}\n\n"
    "Last move: {{last_move}}\n"
    "{{check}}"
)

# ─── Default prompt file paths (relative to project root) ────────────────────
_DEFAULT_SYSTEM_FILE = "prompts/system_prompt.txt"
_DEFAULT_USER_TEMPLATE_FILE = "prompts/user_prompt_template.txt"


# ─── Prompt file helpers ─────────────────────────────────────────────────────
def _read_prompt_file(rel_path: str, fallback: str) -> str:
    """Read a prompt from a file path relative to project root."""
    p = _HERE / rel_path
    if p.exists():
        text = p.read_text(encoding="utf-8").strip()
        if text:
            return text
    return fallback


def _write_prompt_file(rel_path: str, content: str) -> None:
    """Write prompt content to a file, creating directories if needed."""
    p = _HERE / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ─── Response format: file-based with hardcoded fallbacks ────────────────────

def _format_file_path(fmt: str) -> str:
    """Compute the prompts/ file path for a response format name.

    Convention:  ``prompts/format_{fmt}.txt``
    Examples:
        "json_thinking" → "prompts/format_json_thinking.txt"
        "json"          → "prompts/format_json.txt"
        "simple"        → "prompts/format_simple.txt"
    """
    return f"prompts/format_{fmt}.txt"


# Hardcoded fallbacks — used ONLY when the corresponding file does not exist.
DEFAULT_RESPONSE_FORMAT: dict[str, str] = {
    "simple": (
        "Reply with EXACTLY one line: FROM TO\n"
        "Example: W2/R2.3 C/W.R\n"
        "For promotion: W1/B0.2 B3/R3.1 =M\n"
        "Valid promotion pieces: M T D N\n"
        "Use ONLY coordinates from the legal moves list provided."
    ),
    "json": (
        "Respond with a JSON object only (no markdown, no explanation):\n"
        '{"move_from": "W2/R2.3", "move_to": "C/W.R"}\n'
        "For Private promotion:\n"
        '{"move_from": "W1/B0.2", "move_to": "B3/R3.1", "promotion": "marshal"}\n'
        "Promotion values: marshal | train | drone | noctis\n"
        "CRITICAL: Use ONLY coordinates from the legal moves list. "
        "Coordinates are case-sensitive uppercase."
    ),
    "json_thinking": (
        "Respond with a single JSON object. No markdown, no commentary outside JSON.\n\n"
        '{"thinking": "your step-by-step analysis", '
        '"move_from": "W2/R2.3", "move_to": "C/W.R"}\n\n'
        'For Private promotion add: "promotion": "marshal"\n'
        "Promotion values: marshal | train | drone | noctis\n\n"
        "In your thinking, consider:\n"
        "1. Is my Leader safe? Any immediate threats?\n"
        "2. Can I capture an undefended piece or create a fork?\n"
        "3. Does this move improve piece activity (lower buried level)?\n"
        "4. How does this move affect BOTH opponents — am I helping the third player?\n\n"
        "CRITICAL: Use ONLY coordinates from the legal moves list provided. "
        "Coordinates are case-sensitive uppercase."
    ),
}


def get_response_format(fmt: str) -> str:
    """Return the response-format instruction for *fmt*.

    Lookup order:
    1. ``prompts/format_{fmt}.txt`` — if file exists and is non-empty.
    2. Hardcoded ``DEFAULT_RESPONSE_FORMAT[fmt]``.
    3. Hardcoded ``DEFAULT_RESPONSE_FORMAT["json_thinking"]`` (ultimate fallback).
    """
    file_path = _format_file_path(fmt)
    text = _read_prompt_file(file_path, "")
    if text:
        return text
    return DEFAULT_RESPONSE_FORMAT.get(
        fmt, DEFAULT_RESPONSE_FORMAT["json_thinking"]
    )


# ─── Keys that are prompt file paths (not stored as text) ────────────────────
_PROMPT_FILE_KEYS = {"system_prompt_file", "user_template_file"}

# Legacy keys that contained inline prompt text (pre-migration)
_LEGACY_PROMPT_KEYS = {"system_prompt", "user_template"}


# ─── Settings class ──────────────────────────────────────────────────────────
class Settings:
    """JSON-backed application settings.

    Prompt texts are stored in external files (prompts/ directory).
    The JSON settings file stores only the *paths* to prompt files.
    Access ``settings["system_prompt"]`` or ``settings["user_template"]``
    to get the resolved text content (read from file on every access).
    """

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
        "max_tokens": 24000,
        "response_format": "json_thinking",
        "system_prompt_file": _DEFAULT_SYSTEM_FILE,
        "user_template_file": _DEFAULT_USER_TEMPLATE_FILE,
        "additional_rules": "",
        "max_retries": 3,
        "poll_interval": 0.5,
        "auto_skip_waiting": False,
        "fallback_random": True,
        "max_consecutive_fallbacks": 10,
        "min_success_rate_threshold": 0.1,
        "min_moves_for_success_check": 20,
        "use_triumvirate_notation": False,
    }

    def __init__(self) -> None:
        self._d: dict[str, Any] = dict(self.DEFAULTS)
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            stored = json.loads(self._file.read_text(encoding="utf-8"))
        except Exception:
            return

        migrated = self._migrate_legacy_prompts(stored)
        self._d.update(stored)
        if migrated:
            self.save()

    def _migrate_legacy_prompts(self, stored: dict) -> bool:
        """Migrate inline prompt strings to external files.

        If the JSON contains ``system_prompt`` or ``user_template`` as
        string values (legacy format), write them to the corresponding
        prompt files and replace the keys with ``*_file`` paths.

        Returns True if migration occurred (caller should re-save).
        """
        migrated = False

        mapping = {
            "system_prompt": (
                "system_prompt_file",
                _DEFAULT_SYSTEM_FILE,
            ),
            "user_template": (
                "user_template_file",
                _DEFAULT_USER_TEMPLATE_FILE,
            ),
        }

        for old_key, (new_key, default_path) in mapping.items():
            if old_key in stored and isinstance(stored[old_key], str):
                text = stored[old_key]
                file_path = stored.get(new_key, default_path)
                _write_prompt_file(file_path, text)
                del stored[old_key]
                stored[new_key] = file_path
                migrated = True

        return migrated

    def save(self) -> None:
        """Save settings to JSON, excluding inline prompt texts."""
        to_save = {
            k: v
            for k, v in self._d.items()
            if k not in _LEGACY_PROMPT_KEYS
        }
        try:
            self._file.write_text(
                json.dumps(to_save, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _resolve_api_key(self) -> str:
        """Return API key: from JSON settings, or fallback to env var."""
        stored = self._d.get("api_key", "")
        if stored:
            return stored
        provider = self._d.get("provider", "")
        env_name = PROVIDER_ENV_KEY.get(provider, "")
        if env_name:
            return os.environ.get(env_name, "")
        return ""

    def __getitem__(self, key: str) -> Any:
        # Virtual keys: resolve prompt text from files on access
        if key == "system_prompt":
            path = self._d.get(
                "system_prompt_file", _DEFAULT_SYSTEM_FILE
            )
            return _read_prompt_file(path, _FALLBACK_SYSTEM)

        if key == "user_template":
            path = self._d.get(
                "user_template_file", _DEFAULT_USER_TEMPLATE_FILE
            )
            return _read_prompt_file(path, _FALLBACK_USER_TEMPLATE)

        if key == "api_key":
            return self._resolve_api_key()

        return self._d.get(key, self.DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        # Prevent accidentally storing prompt text in JSON
        if key in _LEGACY_PROMPT_KEYS:
            return
        self._d[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        # Route virtual keys through __getitem__
        if key in _LEGACY_PROMPT_KEYS or key == "api_key":
            return self[key]
        return self._d.get(key, default)

    @property
    def system_prompt_path(self) -> Path:
        """Absolute path to the system prompt file."""
        rel = self._d.get("system_prompt_file", _DEFAULT_SYSTEM_FILE)
        return _HERE / rel

    @property
    def user_template_path(self) -> Path:
        """Absolute path to the user template file."""
        rel = self._d.get(
            "user_template_file", _DEFAULT_USER_TEMPLATE_FILE
        )
        return _HERE / rel
