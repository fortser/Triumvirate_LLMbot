"""SmartBot Adapter — изолированный модуль для оценки позиций через SmartBot.

Инкапсулирует все импорты SmartBot. Lazy-загрузка при первом вызове.
Graceful degradation: если SmartBot недоступен — возвращает None.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Путь к SmartBot — из env или fallback
SMARTBOT_DEFAULT_PATH = r"T:\test_python\Triumvirate_Smartbot"
_smartbot_modules: dict[str, Any] = {}  # lazy-cached imports


@dataclass
class MoveEvaluation:
    """Результат оценки одного хода SmartBot."""

    from_coord: str = ""
    to_coord: str = ""
    rating: int = 0
    components: dict[str, int] = field(default_factory=dict)
    gives_check: bool = False
    gives_mate: bool = False
    is_capture: bool = False
    is_defense: bool = False
    exchange_classification: str | None = None
    exchange_net_value: int | None = None
    exchange_is_free: bool | None = None
    threat_addressed: bool = False


@dataclass
class PositionEvaluation:
    """Полный результат оценки позиции SmartBot."""

    # Ход LLM
    llm_rating: int = 0
    llm_rank: int = 0
    llm_components: dict[str, int] = field(default_factory=dict)
    llm_gives_check: bool = False
    llm_gives_mate: bool = False
    llm_is_capture: bool = False
    llm_is_defense: bool = False

    # Лучший ход SmartBot
    best_rating: int = 0
    best_from: str = ""
    best_to: str = ""

    # Разница
    rating_gap: int = 0

    # Общее кол-во оценённых ходов
    total_evaluated: int = 0

    # Все оценённые ходы (топ-5 для контекста)
    top_moves: list[dict] = field(default_factory=list)

    # Threat analysis (Phase 5)
    threats_total: int = 0
    threats_critical: int = 0
    llm_threat_addressed: bool = False
    llm_allows_mate: bool = False
    missed_mate_available: bool = False

    # Game context (Phase 6)
    player_role: str = ""
    material_advantage: int = 0
    game_phase: float = 1.0

    # Exchange (Phase 7)
    llm_exchange_classification: str | None = None
    llm_exchange_net_value: int | None = None
    llm_exchange_is_free: bool | None = None


def _get_smartbot_path() -> str:
    """Возвращает путь к SmartBot из env или fallback."""
    return os.environ.get("SMARTBOT_PATH", SMARTBOT_DEFAULT_PATH)


def is_smartbot_available() -> bool:
    """Проверяет наличие SmartBot и ключевых модулей."""
    path = _get_smartbot_path()
    if not os.path.isdir(path):
        return False
    # Проверяем ключевые подпапки
    for subdir in ("game_io", "evaluation", "bot", "board", "state"):
        if not os.path.isdir(os.path.join(path, subdir)):
            return False
    return True


def _setup_smartbot_path() -> None:
    """Добавляет SmartBot root в sys.path с изоляцией."""
    path = _get_smartbot_path()
    if path not in sys.path:
        # Вставляем в начало, чтобы SmartBot модули имели приоритет
        # при импорте внутри SmartBot (его внутренние import будут работать)
        sys.path.insert(0, path)


def _import_smartbot() -> dict[str, Any]:
    """Lazy import всех нужных SmartBot модулей."""
    global _smartbot_modules
    if _smartbot_modules:
        return _smartbot_modules

    _setup_smartbot_path()

    try:
        from game_io.position_3pf import parse_3pf
        from board.coordinates import Coordinate
        from bot.move_builder import build_move
        from evaluation.threats import find_all_threats
        from evaluation.defense import analyze_defenses
        from evaluation.rating import calculate_move_rating
        from evaluation.tactical import tactical_verify
        from evaluation.selection import select_move
        from evaluation.piece_values import (
            get_game_phase,
            get_player_role,
            get_material_advantage,
        )
        from pieces.base import PlayerColor

        _smartbot_modules = {
            "parse_3pf": parse_3pf,
            "Coordinate": Coordinate,
            "build_move": build_move,
            "find_all_threats": find_all_threats,
            "analyze_defenses": analyze_defenses,
            "calculate_move_rating": calculate_move_rating,
            "tactical_verify": tactical_verify,
            "select_move": select_move,
            "get_game_phase": get_game_phase,
            "get_player_role": get_player_role,
            "get_material_advantage": get_material_advantage,
            "PlayerColor": PlayerColor,
        }
        logger.info("SmartBot modules loaded successfully from %s", _get_smartbot_path())
    except ImportError as e:
        logger.warning("Failed to import SmartBot modules: %s", e)
        raise

    return _smartbot_modules


# Маппинг цвет игрока → PlayerColor
_COLOR_MAP = {
    "white": "WHITE",
    "black": "BLACK",
    "red": "RED",
}


def evaluate_position(
    position_3pf: str,
    legal_moves: dict[str, list[str]],
    llm_from: str,
    llm_to: str,
    player_color: str = "",
) -> PositionEvaluation | None:
    """Оценивает позицию через SmartBot evaluation pipeline.

    Args:
        position_3pf: 3PF строка позиции
        legal_moves: {from_square: [to_square, ...]} в серверной нотации
        llm_from: координата from хода LLM (серверная нотация, e.g. "E2")
        llm_to: координата to хода LLM (серверная нотация, e.g. "E4")
        player_color: цвет игрока ("white"/"black"/"red")

    Returns:
        PositionEvaluation или None при ошибке
    """
    try:
        sb = _import_smartbot()
    except (ImportError, Exception) as e:
        logger.warning("SmartBot not available: %s", e)
        return None

    parse_3pf = sb["parse_3pf"]
    Coordinate = sb["Coordinate"]
    build_move = sb["build_move"]
    find_all_threats = sb["find_all_threats"]
    analyze_defenses = sb["analyze_defenses"]
    calculate_move_rating = sb["calculate_move_rating"]
    tactical_verify = sb["tactical_verify"]
    select_move = sb["select_move"]
    get_game_phase = sb["get_game_phase"]
    get_player_role = sb["get_player_role"]
    get_material_advantage = sb["get_material_advantage"]
    PlayerColor = sb["PlayerColor"]

    # 1. Parse 3PF → GameState
    try:
        game_state = parse_3pf(position_3pf)
    except Exception as e:
        logger.warning("parse_3pf failed: %s", e)
        return None

    # Определяем цвет
    if player_color:
        color_name = _COLOR_MAP.get(player_color.lower(), "")
        if color_name:
            my_color = PlayerColor[color_name]
        else:
            my_color = game_state.current_player
    else:
        my_color = game_state.current_player

    # 2. Find threats & analyze defenses
    try:
        threats = find_all_threats(my_color, game_state)
        threat_summary = analyze_defenses(my_color, game_state, threats)
    except Exception as e:
        logger.warning("Threat analysis failed: %s", e)
        return None

    # 3. Build & rate all legal moves
    rated_moves = []
    for from_sq, to_squares in legal_moves.items():
        for to_sq in to_squares:
            try:
                from_coord = Coordinate(from_sq)
                to_coord = Coordinate(to_sq)
                move = build_move(from_coord, to_coord, game_state)
                if move is None:
                    continue
                rating = calculate_move_rating(move, game_state, threat_summary)
                rated_moves.append(rating)
            except Exception as e:
                logger.debug("Failed to rate move %s→%s: %s", from_sq, to_sq, e)
                continue

    if not rated_moves:
        logger.warning("No moves could be rated for position")
        return None

    # 4. Tactical verification
    try:
        verified = tactical_verify(rated_moves, game_state, my_color)
    except Exception as e:
        logger.warning("Tactical verify failed, using unverified: %s", e)
        verified = rated_moves

    # 5. Sort by rating (descending)
    verified.sort(key=lambda r: r.rating, reverse=True)

    # 6. Find LLM move in verified list
    llm_from_upper = llm_from.upper()
    llm_to_upper = llm_to.upper()
    llm_rating_obj = None
    llm_rank = 0
    for i, r in enumerate(verified, 1):
        if (r.move.from_coord.notation == llm_from_upper
                and r.move.to_coord.notation == llm_to_upper):
            llm_rating_obj = r
            llm_rank = i
            break

    if llm_rating_obj is None:
        # LLM move not found among rated moves — try building it directly
        try:
            llm_move = build_move(
                Coordinate(llm_from_upper),
                Coordinate(llm_to_upper),
                game_state,
            )
            if llm_move:
                llm_rating_obj = calculate_move_rating(
                    llm_move, game_state, threat_summary,
                )
                llm_rank = len(verified) + 1  # worst rank
        except Exception:
            pass

    if llm_rating_obj is None:
        logger.warning("LLM move %s→%s could not be evaluated", llm_from, llm_to)
        return None

    # 7. Best move
    best = verified[0]

    # 8. Game context
    try:
        game_phase = get_game_phase(game_state)
    except Exception:
        game_phase = 1.0

    try:
        player_role_val = get_player_role(my_color, game_state)
        player_role_str = player_role_val.name if hasattr(player_role_val, "name") else str(player_role_val)
    except Exception:
        player_role_str = ""

    try:
        mat_advantage = get_material_advantage(my_color, game_state)
    except Exception:
        mat_advantage = 0

    # 9. Check for missed mate
    any_mate = any(r.gives_mate for r in verified)
    missed_mate = any_mate and not llm_rating_obj.gives_mate

    # 10. Threat info
    threats_total = len(threats)
    threats_critical = threat_summary.critical_threats if hasattr(threat_summary, "critical_threats") else 0
    llm_threat_addressed = llm_rating_obj.threat_addressed is not None

    # 11. Exchange info for LLM move
    llm_exchange_class = None
    llm_exchange_net = None
    llm_exchange_free = None
    if llm_rating_obj.exchange_result is not None:
        ex = llm_rating_obj.exchange_result
        if hasattr(ex, "classification"):
            llm_exchange_class = (
                ex.classification.name
                if hasattr(ex.classification, "name")
                else str(ex.classification)
            )
        if hasattr(ex, "net_value"):
            llm_exchange_net = ex.net_value
        if hasattr(ex, "is_free"):
            llm_exchange_free = ex.is_free

    # 12. Top moves for context
    top_moves = []
    for i, r in enumerate(verified[:5]):
        top_moves.append({
            "rank": i + 1,
            "from": r.move.from_coord.notation,
            "to": r.move.to_coord.notation,
            "rating": r.rating,
            "gives_check": r.gives_check,
            "gives_mate": r.gives_mate,
            "is_capture": r.is_capture,
            "components": dict(r.components) if r.components else {},
        })

    # 13. Assemble result
    result = PositionEvaluation(
        llm_rating=llm_rating_obj.rating,
        llm_rank=llm_rank,
        llm_components=dict(llm_rating_obj.components) if llm_rating_obj.components else {},
        llm_gives_check=llm_rating_obj.gives_check,
        llm_gives_mate=llm_rating_obj.gives_mate,
        llm_is_capture=llm_rating_obj.is_capture,
        llm_is_defense=llm_rating_obj.is_defense,
        best_rating=best.rating,
        best_from=best.move.from_coord.notation,
        best_to=best.move.to_coord.notation,
        rating_gap=best.rating - llm_rating_obj.rating,
        total_evaluated=len(verified),
        top_moves=top_moves,
        threats_total=threats_total,
        threats_critical=threats_critical,
        llm_threat_addressed=llm_threat_addressed,
        llm_allows_mate=False,  # Phase 5: requires heavy check
        missed_mate_available=missed_mate,
        player_role=player_role_str,
        material_advantage=mat_advantage,
        game_phase=game_phase,
        llm_exchange_classification=llm_exchange_class,
        llm_exchange_net_value=llm_exchange_net,
        llm_exchange_is_free=llm_exchange_free,
    )

    return result
