"""Загрузчик и нормализатор trace-файлов.

Сканирует папку logs/, парсит JSON, нормализует в плоский список.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def scan_traces(logs_dir: str | Path) -> list[dict]:
    """Рекурсивно читает все move_*.json из logs/game_*/ папок.

    Возвращает список нормализованных записей, отсортированных
    по (game_id, move_number).
    """
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return []

    raw_traces: list[dict] = []
    for json_file in sorted(logs_path.rglob("move_*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            data["_source_file"] = str(json_file)
            raw_traces.append(data)
        except Exception:
            continue

    return [_normalize(t) for t in raw_traces]


def _normalize(raw: dict) -> dict:
    """Извлекает ключевые поля в плоскую структуру."""
    stats = raw.get("statistics") or {}
    pricing = raw.get("model_pricing") or {}
    move_sel = raw.get("move_selected") or {}
    pipeline = raw.get("prompt_pipeline") or {}

    # Извлечение модели из server_state_raw → players
    model = _extract_model(raw)

    # Извлечение thinking из первого LLM-ответа
    thinking = _extract_thinking(raw)

    game_id = raw.get("game_id", "unknown")

    return {
        # Идентификаторы
        "game_id": game_id,
        "game_id_short": game_id[:8] if game_id else "?",
        "move_number": raw.get("move_number", 0),
        "model": model,
        "outcome": raw.get("outcome", "unknown"),
        "source_file": raw.get("_source_file", ""),
        # Тайминги
        "time_total": stats.get("time_total_sec", 0.0),
        "llm_time": stats.get("llm_time_sec", 0.0),
        # Токены
        "prompt_tokens": stats.get("total_prompt_tokens", 0),
        "completion_tokens": stats.get("total_completion_tokens", 0),
        "reasoning_tokens": stats.get("total_reasoning_tokens", 0),
        "total_tokens": stats.get("total_tokens", 0),
        # Стоимость
        "cost_usd": stats.get("total_cost_usd", 0.0),
        # Ретраи
        "retries": stats.get("retries", 0),
        "llm_calls": stats.get("llm_calls", 0),
        # Thinking
        "thinking": thinking,
        "thinking_length": len(thinking),
        # Выбранный ход
        "move_from": move_sel.get("from", ""),
        "move_to": move_sel.get("to", ""),
        "promotion": move_sel.get("promotion"),
        # Prompt pipeline
        "system_prompt_template": pipeline.get("system_prompt", ""),
        "user_template": pipeline.get("user_template", ""),
        "rendered_system": pipeline.get("rendered_system", ""),
        "rendered_user": pipeline.get("rendered_user_prompt", ""),
        "additional_rules": pipeline.get("additional_rules", ""),
        "response_format_instruction": pipeline.get(
            "response_format_instruction", ""
        ),
        # Pricing
        "pricing_source": pricing.get("source", ""),
        "prompt_per_1m": pricing.get("prompt_per_1m_usd", 0.0),
        "completion_per_1m": pricing.get("completion_per_1m_usd", 0.0),
        # Raw — полный оригинал для детального просмотра
        "raw_trace": raw,
    }


def _extract_model(raw: dict) -> str:
    """Извлекает имя модели из данных игроков или prompt_pipeline."""
    state = raw.get("server_state_raw") or {}
    players = state.get("players") or []
    current = state.get("current_player", "")

    for p in players:
        if p.get("color") == current and p.get("model"):
            return p["model"]

    # Fallback: из имени папки (game_<id>__<model>)
    src = raw.get("_source_file", "")
    m = re.search(r"game_[^_]+__(.+?)[\\/]", src)
    if m:
        return m.group(1)

    return "unknown"


def _extract_thinking(raw: dict) -> str:
    """Извлекает текст рассуждений из первого LLM-ответа.

    LLM response хранится как строка в raw_response.
    Если это JSON с полем thinking — извлекаем его.
    """
    responses = raw.get("llm_responses") or []
    if not responses:
        return ""

    raw_resp = responses[0].get("raw_response", "")
    if not raw_resp:
        return ""

    # Попытка распарсить как JSON и достать thinking
    try:
        start = raw_resp.find("{")
        end = raw_resp.rfind("}")
        if start != -1 and end > start:
            obj = json.loads(raw_resp[start : end + 1])
            thinking = obj.get("thinking", "")
            if thinking:
                return str(thinking)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback — весь текст ответа
    return raw_resp


def get_games_summary(traces: list[dict]) -> list[dict]:
    """Агрегация метрик по каждой игре."""
    games: dict[str, list[dict]] = {}
    for t in traces:
        gid = t["game_id"]
        games.setdefault(gid, []).append(t)

    summaries = []
    for gid, moves in games.items():
        times = [m["llm_time"] for m in moves if m["llm_time"] > 0]
        costs = [m["cost_usd"] for m in moves]
        tokens = [m["total_tokens"] for m in moves]
        outcomes = [m["outcome"] for m in moves]

        success_count = sum(1 for o in outcomes if o == "success")
        retry_count = sum(1 for m in moves if m["retries"] > 0)
        fallback_count = sum(
            1 for o in outcomes if o == "fallback_random"
        )

        summaries.append(
            {
                "game_id": gid,
                "game_id_short": gid[:8],
                "model": moves[0]["model"] if moves else "?",
                "total_moves": len(moves),
                "total_cost": sum(costs),
                "avg_cost": sum(costs) / len(costs) if costs else 0,
                "avg_time": sum(times) / len(times) if times else 0,
                "median_time": sorted(times)[len(times) // 2]
                if times
                else 0,
                "max_time": max(times) if times else 0,
                "total_tokens": sum(tokens),
                "avg_tokens": sum(tokens) / len(tokens) if tokens else 0,
                "success_rate": success_count / len(moves) * 100
                if moves
                else 0,
                "retry_rate": retry_count / len(moves) * 100
                if moves
                else 0,
                "fallback_rate": fallback_count / len(moves) * 100
                if moves
                else 0,
            }
        )

    return sorted(summaries, key=lambda s: s["game_id"])
