"""Pure functions extracted from gui.py for testability.

These functions contain business logic that was originally embedded
inside gui.py closures. They are imported by gui.py and tested directly.
"""
from __future__ import annotations

import json
import os
from typing import Any


def format_state_text(state: dict) -> tuple[str, str]:
    """Format game state into markdown strings for display.

    Returns:
        (state_md, legal_md) — state summary and legal moves text.
    """
    move_num = state.get("move_number", 0)
    current = state.get("current_player", "?")
    gst = state.get("game_status", "?")
    last = state.get("last_move")
    last_text = (
        f"{last['from_square']}\u2192{last['to_square']}" if last else "\u2014"
    )
    check = state.get("check") or {}
    check_str = ""
    if check.get("is_check"):
        check_str = (
            f"  \u26a0\ufe0f CHECK: {', '.join(check.get('checked_colors', []))}"
        )
    state_md = (
        f"**\u0425\u043e\u0434 #{move_num}** | \u0425\u043e\u0434\u0438\u0442: "
        f"**{current.upper()}** | \u0421\u0442\u0430\u0442\u0443\u0441: *{gst}*"
        f"{check_str}\n\n"
        f"\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0439 \u0445\u043e\u0434: "
        f"`{last_text}`"
    )

    legal = state.get("legal_moves", {})
    if legal:
        lines = [
            f"`{src}` \u2192 {', '.join(f'`{d}`' for d in sorted(dsts))}"
            for src, dsts in sorted(legal.items())
        ]
        legal_md = "\n\n".join(lines)
    else:
        legal_md = "*(\u043d\u0435\u0442 \u0434\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u0445 \u0445\u043e\u0434\u043e\u0432)*"

    return state_md, legal_md


def format_game_list(games: list[dict]) -> str:
    """Format a list of games into markdown."""
    if not games:
        return "*(\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0438\u0433\u0440 \u043d\u0435\u0442)*"
    lines = []
    for g in games:
        gid = g.get("game_id", "?")[:8]
        players = ", ".join(
            f"{p.get('color', '?')}:{p.get('name', '?')}"
            for p in g.get("players", [])
        )
        mn = g.get("move_number", 0)
        lines.append(f"**{gid}\u2026** | {players} | \u0445\u043e\u0434 {mn}")
    return "\n\n".join(lines)


def collect_settings(values: dict, provider_env_key: dict) -> dict:
    """Build a settings dict from UI values.

    Args:
        values: dict of UI field values (provider, api_key, custom_headers, etc.)
        provider_env_key: PROVIDER_ENV_KEY mapping.

    Returns:
        dict ready to update Settings.
    """
    result = dict(values)

    # API key fallback to env
    api_key = result.get("api_key", "").strip()
    if not api_key:
        provider = result.get("provider", "")
        env_var = provider_env_key.get(provider, "")
        if env_var:
            api_key = os.environ.get(env_var, "")
    result["api_key"] = api_key

    # Custom headers JSON parsing
    raw_ch = result.get("custom_headers", "")
    if isinstance(raw_ch, str):
        raw_ch = raw_ch.strip()
        if raw_ch:
            try:
                result["custom_headers"] = json.loads(raw_ch)
            except json.JSONDecodeError:
                result["custom_headers"] = {}
        else:
            result["custom_headers"] = {}

    # Strip whitespace from string values
    for key in ("server_url", "bot_name", "model", "base_url"):
        if key in result and isinstance(result[key], str):
            result[key] = result[key].strip()

    return result


def apply_provider_preset(provider: str, providers: dict) -> dict:
    """Get preset values when switching provider.

    Returns dict of field values to apply, or empty dict if unknown.
    """
    if provider not in providers:
        return {}
    info = providers[provider]
    result: dict[str, Any] = {
        "base_url": info["base_url"],
        "model": info["model"],
        "compat": info.get("compat", True),
    }
    if "temperature" in info:
        result["temperature"] = info["temperature"]
    if "max_tokens" in info:
        result["max_tokens"] = info["max_tokens"]
    if "response_format" in info:
        result["response_format"] = info["response_format"]
    ch = info.get("custom_headers", {})
    result["custom_headers"] = json.dumps(ch, ensure_ascii=False) if ch else ""
    result["api_key_preset"] = info.get("api_key", "")
    return result


def mask_api_key(key: str) -> str:
    """Mask an API key for display."""
    if not key:
        return ""
    if len(key) > 12:
        return f"{key[:8]}...{key[-4:]}"
    return "***"


def format_hint(fmt: str) -> str:
    """Get format hint text for a response format."""
    hints = {
        "simple": "\u041e\u0442\u0432\u0435\u0442: \u00abE2 E4\u00bb",
        "json": '\u041e\u0442\u0432\u0435\u0442: {"from":"E2","to":"E4"}',
        "json_thinking": '\u041e\u0442\u0432\u0435\u0442: {"thinking":"\u2026","from":"E2","to":"E4"}',
    }
    return hints.get(fmt, "")
