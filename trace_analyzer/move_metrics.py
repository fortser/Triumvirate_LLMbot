"""Per-move автоматические метрики.

Вычисляет детерминированные метрики для каждого хода из трейс-файла.
Не использует LLM — только данные из трейса + notation_converter.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# notation_converter лежит в корне проекта — добавляем в path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from notation_converter import parse_triumvirate, to_triumvirate

# Стоимость фигур для material delta
PIECE_VALUES: dict[str, int] = {
    "P": 1,
    "N": 3,
    "B": 3,
    "R": 5,
    "Q": 9,
    "K": 0,  # Leader не имеет материальной стоимости
}


@dataclass
class MoveMetrics:
    """Автоматические метрики одного хода."""

    # Идентификаторы
    game_id: str = ""
    move_number: int = 0
    model: str = ""
    timestamp: str = ""

    # Outcome
    outcome: str = ""  # success / fallback_random / error
    is_check: bool = False
    is_checkmate: bool = False
    is_stalemate: bool = False
    eliminated_player: str | None = None
    game_over: bool = False
    winner: str | None = None

    # Buried level
    move_from_tri: str = ""
    move_to_tri: str = ""
    buried_from: int = -1  # -1 = не удалось вычислить
    buried_to: int = -1
    buried_delta: int = 0  # >0 = улучшение (к центру)
    is_rosette_move: bool = False

    # Captures & material
    is_capture: bool = False
    captured_piece_type: str | None = None
    material_delta: int = 0

    # Promotion
    is_promotion: bool = False

    # Legal moves
    legal_moves_count: int = 0  # общее кол-во вариантов

    # Reliability
    retries: int = 0
    llm_calls: int = 0
    first_attempt_success: bool = False

    # Cost & performance
    cost_usd: float = 0.0
    time_total_sec: float = 0.0
    llm_time_sec: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    # Thinking
    thinking_length: int = 0
    has_thinking: bool = False

    # Цвет игрока
    player_color: str = ""

    # SmartBot evaluation
    smartbot_available: bool = False
    smartbot_llm_rating: int = 0
    smartbot_best_rating: int = 0
    smartbot_rating_gap: int = 0
    smartbot_llm_rank: int = 0
    smartbot_total_evaluated: int = 0
    smartbot_move_category: str = ""  # brilliant/good/inaccuracy/mistake/blunder/forced

    # SmartBot components
    smartbot_material: int = 0
    smartbot_defense: int = 0
    smartbot_tactical: int = 0
    smartbot_positional: int = 0
    smartbot_risk: int = 0

    # SmartBot context
    smartbot_threats_total: int = 0
    smartbot_threats_critical: int = 0
    smartbot_threat_addressed: bool = False
    smartbot_allows_mate: bool = False
    smartbot_missed_mate: bool = False
    smartbot_material_advantage: int = 0
    smartbot_player_role: str = ""
    smartbot_game_phase: float = 0.0

    # Exchange quality
    smartbot_exchange_classification: str | None = None
    smartbot_exchange_net_value: int | None = None
    smartbot_exchange_is_free: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_move(llm_rating: int, best_rating: int, total_moves: int) -> str:
    """Классифицирует ход LLM по шкале качества.

    Returns:
        brilliant/good/inaccuracy/mistake/blunder/forced/losing_position
    """
    if total_moves <= 1:
        return "forced"
    if best_rating <= 0 and llm_rating <= 0:
        return "losing_position"

    gap = best_rating - llm_rating
    if gap <= 0:
        return "brilliant"

    ratio = llm_rating / max(best_rating, 1)
    if ratio >= 0.90:
        return "good"
    if ratio >= 0.60:
        return "inaccuracy"
    if ratio >= 0.20:
        return "mistake"
    return "blunder"


def compute_move_metrics(
    raw_trace: dict,
    smartbot_eval: dict | None = None,
) -> MoveMetrics:
    """Вычисляет метрики из сырого трейс-файла (JSON)."""
    m = MoveMetrics()

    # === Идентификаторы ===
    m.game_id = raw_trace.get("game_id", "")
    m.move_number = raw_trace.get("move_number", 0)
    m.timestamp = raw_trace.get("timestamp", "")
    m.outcome = raw_trace.get("outcome", "unknown")

    # Модель и цвет
    state = raw_trace.get("server_state_raw") or {}
    m.player_color = state.get("current_player", "")
    m.model = _extract_model(raw_trace, state)

    # === Server move response ===
    smr_data = (raw_trace.get("server_move_response") or {}).get("data") or {}
    m.is_check = bool(smr_data.get("is_check"))
    m.is_checkmate = bool(smr_data.get("is_checkmate"))
    m.is_stalemate = bool(smr_data.get("is_stalemate"))
    m.eliminated_player = smr_data.get("eliminated_player")
    m.game_over = bool(smr_data.get("game_over"))
    m.winner = smr_data.get("winner")

    # === Move selected (buried level) ===
    move_sel = raw_trace.get("move_selected") or {}
    m.move_from_tri = move_sel.get("from", "")
    m.move_to_tri = move_sel.get("to", "")
    m.is_promotion = move_sel.get("promotion") is not None

    _compute_buried(m)

    # === Capture detection ===
    board_before = state.get("board") or []
    board_after_state = smr_data.get("state") or {}
    board_after = board_after_state.get("board") or []
    _compute_capture(m, board_before, board_after)

    # === Legal moves count ===
    legal = state.get("legal_moves") or {}
    m.legal_moves_count = sum(len(v) for v in legal.values())

    # === Statistics ===
    stats = raw_trace.get("statistics") or {}
    m.retries = stats.get("retries", 0)
    m.llm_calls = stats.get("llm_calls", 0)
    m.cost_usd = stats.get("total_cost_usd", 0.0)
    m.time_total_sec = stats.get("time_total_sec", 0.0)
    m.llm_time_sec = stats.get("llm_time_sec", 0.0)
    m.prompt_tokens = stats.get("total_prompt_tokens", 0)
    m.completion_tokens = stats.get("total_completion_tokens", 0)
    m.reasoning_tokens = stats.get("total_reasoning_tokens", 0)
    m.total_tokens = stats.get("total_tokens", 0)

    # === Parser ===
    parser = raw_trace.get("parser_attempts") or []
    m.first_attempt_success = bool(parser and parser[0].get("valid"))

    # === Thinking ===
    m.thinking_length = _thinking_length(raw_trace)
    m.has_thinking = m.thinking_length > 0

    # === SmartBot evaluation ===
    if smartbot_eval and smartbot_eval.get("smartbot_available"):
        m.smartbot_available = True
        m.smartbot_llm_rating = smartbot_eval.get("smartbot_llm_rating", 0)
        m.smartbot_best_rating = smartbot_eval.get("smartbot_best_rating", 0)
        m.smartbot_rating_gap = smartbot_eval.get("smartbot_rating_gap", 0)
        m.smartbot_llm_rank = smartbot_eval.get("smartbot_llm_rank", 0)
        m.smartbot_total_evaluated = smartbot_eval.get("smartbot_total_evaluated", 0)
        # Components
        m.smartbot_material = smartbot_eval.get("smartbot_material", 0)
        m.smartbot_defense = smartbot_eval.get("smartbot_defense", 0)
        m.smartbot_tactical = smartbot_eval.get("smartbot_tactical", 0)
        m.smartbot_positional = smartbot_eval.get("smartbot_positional", 0)
        m.smartbot_risk = smartbot_eval.get("smartbot_risk", 0)
        # Context
        m.smartbot_threats_total = smartbot_eval.get("smartbot_threats_total", 0)
        m.smartbot_threats_critical = smartbot_eval.get("smartbot_threats_critical", 0)
        m.smartbot_threat_addressed = smartbot_eval.get("smartbot_threat_addressed", False)
        m.smartbot_allows_mate = smartbot_eval.get("smartbot_allows_mate", False)
        m.smartbot_missed_mate = smartbot_eval.get("smartbot_missed_mate", False)
        m.smartbot_material_advantage = smartbot_eval.get("smartbot_material_advantage", 0)
        m.smartbot_player_role = smartbot_eval.get("smartbot_player_role", "")
        m.smartbot_game_phase = smartbot_eval.get("smartbot_game_phase", 0.0)
        # Exchange
        m.smartbot_exchange_classification = smartbot_eval.get("smartbot_exchange_classification")
        m.smartbot_exchange_net_value = smartbot_eval.get("smartbot_exchange_net_value")
        m.smartbot_exchange_is_free = smartbot_eval.get("smartbot_exchange_is_free")
        # Category
        m.smartbot_move_category = classify_move(
            m.smartbot_llm_rating,
            m.smartbot_best_rating,
            m.smartbot_total_evaluated,
        )

    return m


def _extract_model(raw: dict, state: dict) -> str:
    """Извлекает имя модели."""
    players = state.get("players") or []
    current = state.get("current_player", "")
    for p in players:
        if p.get("color") == current and p.get("model"):
            return p["model"]
    # Fallback из имени папки
    import re

    src = raw.get("_source_file", "")
    match = re.search(r"game_[^_]+__(.+?)[\\/]", src)
    return match.group(1).replace("_", "/", 1) if match else "unknown"


def _compute_buried(m: MoveMetrics) -> None:
    """Вычисляет buried level для from и to."""
    if not m.move_from_tri or not m.move_to_tri:
        return
    try:
        pf = parse_triumvirate(m.move_from_tri)
        pt = parse_triumvirate(m.move_to_tri)
        m.buried_from = pf["buried"]
        m.buried_to = pt["buried"]
        m.buried_delta = m.buried_from - m.buried_to  # >0 = к центру
        m.is_rosette_move = pt["rosette"]
    except (KeyError, ValueError, IndexError):
        pass


def _compute_capture(
    m: MoveMetrics, board_before: list[dict], board_after: list[dict],
) -> None:
    """Определяет capture сравнением board before/after."""
    if not board_before or not board_after:
        return

    # Серверная нотация move_to
    try:
        if m.move_to_tri:
            from notation_converter import to_server

            move_to_server = to_server(m.move_to_tri)
        else:
            return
    except KeyError:
        return

    # Ищем фигуру на целевой клетке ДО хода
    for piece in board_before:
        if piece.get("notation") == move_to_server:
            if piece.get("color") != m.player_color:
                m.is_capture = True
                m.captured_piece_type = piece.get("type")
                m.material_delta = PIECE_VALUES.get(
                    m.captured_piece_type or "", 0
                )
            break


def _thinking_length(raw: dict) -> int:
    """Длина thinking-блока из первого LLM-ответа."""
    import json as _json

    responses = raw.get("llm_responses") or []
    if not responses:
        return 0
    raw_resp = responses[0].get("raw_response", "")
    if not raw_resp:
        return 0
    try:
        start = raw_resp.find("{")
        end = raw_resp.rfind("}")
        if start != -1 and end > start:
            obj = _json.loads(raw_resp[start : end + 1])
            thinking = obj.get("thinking", "")
            if thinking:
                return len(str(thinking))
    except (ValueError, _json.JSONDecodeError):
        pass
    return len(raw_resp)
