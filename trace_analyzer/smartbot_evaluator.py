"""SmartBot Evaluator — массовая оценка трейсов через SmartBot.

Прогоняет SmartBot evaluation по всем ходам из трейс-файлов.
Поддерживает кэширование по position_3pf.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict
from typing import Any

from trace_analyzer.smartbot_adapter import (
    PositionEvaluation,
    evaluate_position,
    is_smartbot_available,
)

logger = logging.getLogger(__name__)


def evaluate_traces(
    raw_traces: list[dict],
    *,
    check_mates: bool = False,
    progress_every: int = 100,
) -> list[dict[str, Any]]:
    """Оценивает все ходы из сырых трейсов через SmartBot.

    Args:
        raw_traces: список сырых трейсов (JSON dicts)
        check_mates: включить проверку мата (тяжёлое вычисление)
        progress_every: печатать прогресс каждые N ходов

    Returns:
        Список dict с SmartBot-полями для каждого хода.
        Каждый dict содержит game_id, move_number и smartbot_* поля.
    """
    if not is_smartbot_available():
        logger.warning("SmartBot not available, skipping evaluation")
        return []

    results: list[dict[str, Any]] = []
    cache: dict[str, PositionEvaluation | None] = {}
    t0 = time.time()
    evaluated = 0
    skipped = 0
    cached_hits = 0

    for i, raw in enumerate(raw_traces):
        if progress_every and (i + 1) % progress_every == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info(
                "Progress: %d/%d traces (%.1f/s), %d evaluated, %d skipped, %d cache hits",
                i + 1, len(raw_traces), rate, evaluated, skipped, cached_hits,
            )

        # Извлекаем данные из трейса
        game_id = raw.get("game_id", "")
        move_number = raw.get("move_number", 0)
        outcome = raw.get("outcome", "")

        # Пропуск ходов с ошибками сервера
        if "error" in outcome and "fallback" not in outcome:
            skipped += 1
            results.append(_empty_result(game_id, move_number))
            continue

        state = raw.get("server_state_raw") or {}
        position_3pf = state.get("position_3pf", "")
        legal_moves = state.get("legal_moves") or {}
        player_color = state.get("current_player", "")

        if not position_3pf:
            logger.debug(
                "No position_3pf in trace game=%s move=%d, skipping",
                game_id, move_number,
            )
            skipped += 1
            results.append(_empty_result(game_id, move_number))
            continue

        # Извлекаем from/to из server_move_request (всегда серверная нотация)
        smr = raw.get("server_move_request") or {}
        llm_from = smr.get("from", "")
        llm_to = smr.get("to", "")

        if not llm_from or not llm_to:
            skipped += 1
            results.append(_empty_result(game_id, move_number))
            continue

        # Кэш по position_3pf + ход LLM
        cache_key = f"{position_3pf}|{llm_from}|{llm_to}"
        if cache_key in cache:
            cached_hits += 1
            eval_result = cache[cache_key]
        else:
            eval_result = evaluate_position(
                position_3pf=position_3pf,
                legal_moves=legal_moves,
                llm_from=llm_from,
                llm_to=llm_to,
                player_color=player_color,
            )
            cache[cache_key] = eval_result

        if eval_result is None:
            skipped += 1
            results.append(_empty_result(game_id, move_number))
            continue

        evaluated += 1
        results.append(_eval_to_dict(game_id, move_number, eval_result))

    elapsed = time.time() - t0
    logger.info(
        "SmartBot evaluation complete: %d evaluated, %d skipped, %d cache hits in %.1fs",
        evaluated, skipped, cached_hits, elapsed,
    )

    return results


def _empty_result(game_id: str, move_number: int) -> dict[str, Any]:
    """Пустой результат для пропущенного хода."""
    return {
        "game_id": game_id,
        "move_number": move_number,
        "smartbot_available": False,
    }


def _eval_to_dict(
    game_id: str, move_number: int, ev: PositionEvaluation,
) -> dict[str, Any]:
    """Конвертирует PositionEvaluation в flat dict с smartbot_ префиксом."""
    return {
        "game_id": game_id,
        "move_number": move_number,
        "smartbot_available": True,
        "smartbot_llm_rating": ev.llm_rating,
        "smartbot_best_rating": ev.best_rating,
        "smartbot_rating_gap": ev.rating_gap,
        "smartbot_llm_rank": ev.llm_rank,
        "smartbot_total_evaluated": ev.total_evaluated,
        # Components
        "smartbot_material": ev.llm_components.get("material", 0),
        "smartbot_defense": ev.llm_components.get("defense", 0),
        "smartbot_tactical": ev.llm_components.get("tactical", 0),
        "smartbot_positional": ev.llm_components.get("positional", 0),
        "smartbot_risk": ev.llm_components.get("risk", 0),
        # LLM move details
        "smartbot_gives_check": ev.llm_gives_check,
        "smartbot_gives_mate": ev.llm_gives_mate,
        "smartbot_is_capture": ev.llm_is_capture,
        "smartbot_is_defense": ev.llm_is_defense,
        # Best move
        "smartbot_best_from": ev.best_from,
        "smartbot_best_to": ev.best_to,
        # Threats
        "smartbot_threats_total": ev.threats_total,
        "smartbot_threats_critical": ev.threats_critical,
        "smartbot_threat_addressed": ev.llm_threat_addressed,
        "smartbot_allows_mate": ev.llm_allows_mate,
        "smartbot_missed_mate": ev.missed_mate_available,
        # Game context
        "smartbot_player_role": ev.player_role,
        "smartbot_material_advantage": ev.material_advantage,
        "smartbot_game_phase": ev.game_phase,
        # Exchange
        "smartbot_exchange_classification": ev.llm_exchange_classification,
        "smartbot_exchange_net_value": ev.llm_exchange_net_value,
        "smartbot_exchange_is_free": ev.llm_exchange_is_free,
        # Top moves for debugging
        "smartbot_top_moves": ev.top_moves,
    }
