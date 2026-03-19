"""Агрегация метрик per-model, per-game и composite score.

Работает с результатами move_metrics.compute_move_metrics().
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean, median, quantiles
from typing import Any


@dataclass
class ModelStats:
    """Агрегированные метрики одной модели."""

    model: str = ""
    total_games: int = 0
    total_moves: int = 0

    # Reliability
    success_rate: float = 0.0
    fallback_rate: float = 0.0
    retry_rate: float = 0.0
    first_attempt_rate: float = 0.0

    # Cost & performance
    total_cost: float = 0.0
    avg_cost_per_move: float = 0.0
    avg_time_per_move: float = 0.0
    median_time_per_move: float = 0.0
    avg_tokens_per_move: float = 0.0

    # Activity
    avg_buried_delta: float = 0.0
    rosette_move_rate: float = 0.0

    # Tactical
    check_rate: float = 0.0
    capture_rate: float = 0.0
    avg_material_delta: float = 0.0

    # Thinking
    avg_thinking_length: float = 0.0

    # Game outcomes
    games_won: int = 0
    games_eliminated: int = 0
    win_rate: float = 0.0
    survival_rate: float = 0.0
    avg_moves_per_game: float = 0.0

    # Composite
    reliability_score: float = 0.0
    activity_score: float = 0.0
    tactical_score: float = 0.0
    efficiency_score: float = 0.0
    auto_composite: float = 0.0
    rank: int = 0

    # SmartBot quality metrics
    smartbot_avg_rating_gap: float = 0.0
    smartbot_median_rating_gap: float = 0.0
    smartbot_p90_rating_gap: float = 0.0
    smartbot_rank_1_rate: float = 0.0
    smartbot_top3_rate: float = 0.0
    smartbot_blunder_rate: float = 0.0
    smartbot_brilliant_rate: float = 0.0
    smartbot_allows_mate_rate: float = 0.0
    smartbot_threat_addressed_rate: float = 0.0
    smartbot_missed_mate_count: int = 0

    # Move category distribution
    smartbot_cat_brilliant: float = 0.0
    smartbot_cat_good: float = 0.0
    smartbot_cat_inaccuracy: float = 0.0
    smartbot_cat_mistake: float = 0.0
    smartbot_cat_blunder: float = 0.0

    # Component weakness profile
    smartbot_avg_material: float = 0.0
    smartbot_avg_defense: float = 0.0
    smartbot_avg_tactical: float = 0.0
    smartbot_avg_positional: float = 0.0
    smartbot_avg_risk: float = 0.0

    # Overall SmartBot quality score
    smartbot_quality_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GameResult:
    """Результат одной игры."""

    game_id: str = ""
    model: str = ""
    player_color: str = ""
    total_moves: int = 0
    game_result: str = ""  # win / eliminated / playing / unknown
    final_move_number: int = 0
    total_cost: float = 0.0
    total_time: float = 0.0
    checks_delivered: int = 0
    captures_made: int = 0
    fallback_count: int = 0
    avg_buried_delta: float = 0.0

    # SmartBot per-game
    smartbot_avg_rating_gap: float = 0.0
    smartbot_blunder_count: int = 0
    smartbot_allows_mate_count: int = 0
    smartbot_avg_material_advantage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def aggregate_by_game(moves: list[dict]) -> list[GameResult]:
    """Агрегирует move-метрики в per-game результаты."""
    games: dict[str, list[dict]] = {}
    for m in moves:
        gid = m["game_id"]
        games.setdefault(gid, []).append(m)

    results = []
    for gid, gm in games.items():
        gm_sorted = sorted(gm, key=lambda x: x["move_number"])
        last = gm_sorted[-1]

        # Определяем game_result из последнего хода
        game_result = "playing"
        if last.get("game_over"):
            if last.get("winner"):
                color = gm_sorted[0].get("player_color", "")
                if last["winner"] == color:
                    game_result = "win"
                else:
                    game_result = "loss"
            else:
                game_result = "draw"
        # Проверяем eliminated по всем ходам
        color = gm_sorted[0].get("player_color", "")
        for mm in gm_sorted:
            if mm.get("eliminated_player") == color:
                game_result = "eliminated"
                break

        success_moves = [m for m in gm if m["outcome"] == "success"]
        deltas = [
            m["buried_delta"]
            for m in success_moves
            if m.get("buried_from", -1) >= 0
        ]

        # SmartBot per-game
        sb_moves = [m for m in gm if m.get("smartbot_available")]
        sb_gaps = [m["smartbot_rating_gap"] for m in sb_moves]
        sb_blunders = sum(
            1 for m in sb_moves if m.get("smartbot_move_category") == "blunder"
        )
        sb_mate = sum(1 for m in sb_moves if m.get("smartbot_allows_mate"))
        sb_mat_adv = [m["smartbot_material_advantage"] for m in sb_moves]

        results.append(
            GameResult(
                game_id=gid,
                model=gm_sorted[0].get("model", ""),
                player_color=color,
                total_moves=len(gm),
                game_result=game_result,
                final_move_number=last["move_number"],
                total_cost=sum(m["cost_usd"] for m in gm),
                total_time=sum(m["llm_time_sec"] for m in gm),
                checks_delivered=sum(1 for m in gm if m.get("is_check")),
                captures_made=sum(1 for m in gm if m.get("is_capture")),
                fallback_count=sum(
                    1 for m in gm if m["outcome"].startswith("fallback_random")
                ),
                avg_buried_delta=mean(deltas) if deltas else 0.0,
                smartbot_avg_rating_gap=mean(sb_gaps) if sb_gaps else 0.0,
                smartbot_blunder_count=sb_blunders,
                smartbot_allows_mate_count=sb_mate,
                smartbot_avg_material_advantage=mean(sb_mat_adv) if sb_mat_adv else 0.0,
            )
        )

    return sorted(results, key=lambda r: r.game_id)


def aggregate_by_model(
    moves: list[dict], game_results: list[GameResult],
) -> list[ModelStats]:
    """Агрегирует move-метрики в per-model статистику."""
    by_model: dict[str, list[dict]] = {}
    for m in moves:
        by_model.setdefault(m["model"], []).append(m)

    games_by_model: dict[str, list[GameResult]] = {}
    for gr in game_results:
        games_by_model.setdefault(gr.model, []).append(gr)

    stats_list = []
    for model, mm in by_model.items():
        s = ModelStats(model=model)
        s.total_moves = len(mm)

        model_games = games_by_model.get(model, [])
        s.total_games = len(model_games)

        # Reliability
        success = [m for m in mm if m["outcome"] == "success"]
        fallback = [m for m in mm if m["outcome"].startswith("fallback_random")]
        with_retries = [m for m in mm if m["retries"] > 0]
        first_ok = [m for m in mm if m.get("first_attempt_success")]

        n = s.total_moves or 1
        s.success_rate = len(success) / n
        s.fallback_rate = len(fallback) / n
        s.retry_rate = len(with_retries) / n
        s.first_attempt_rate = len(first_ok) / n

        # Cost & performance
        s.total_cost = sum(m["cost_usd"] for m in mm)
        s.avg_cost_per_move = s.total_cost / n
        times = [m["llm_time_sec"] for m in mm if m["llm_time_sec"] > 0]
        s.avg_time_per_move = mean(times) if times else 0.0
        s.median_time_per_move = median(times) if times else 0.0
        tokens = [m["total_tokens"] for m in mm if m["total_tokens"] > 0]
        s.avg_tokens_per_move = mean(tokens) if tokens else 0.0

        # Activity (только success-ходы)
        deltas = [
            m["buried_delta"]
            for m in success
            if m.get("buried_from", -1) >= 0
        ]
        s.avg_buried_delta = mean(deltas) if deltas else 0.0
        rosette = sum(1 for m in success if m.get("is_rosette_move"))
        ns = len(success) or 1
        s.rosette_move_rate = rosette / ns

        # Tactical
        checks = sum(1 for m in mm if m.get("is_check"))
        captures = sum(1 for m in mm if m.get("is_capture"))
        s.check_rate = checks / ns
        s.capture_rate = captures / ns
        mat_deltas = [
            m["material_delta"] for m in mm if m.get("is_capture")
        ]
        s.avg_material_delta = mean(mat_deltas) if mat_deltas else 0.0

        # Thinking
        thinking = [m["thinking_length"] for m in mm]
        s.avg_thinking_length = mean(thinking) if thinking else 0.0

        # Game outcomes
        s.games_won = sum(1 for g in model_games if g.game_result == "win")
        s.games_eliminated = sum(
            1 for g in model_games if g.game_result == "eliminated"
        )
        ng = s.total_games or 1
        s.win_rate = s.games_won / ng
        s.survival_rate = (ng - s.games_eliminated) / ng
        s.avg_moves_per_game = s.total_moves / ng

        # SmartBot metrics
        sb_moves = [m for m in mm if m.get("smartbot_available")]
        if sb_moves:
            nsb = len(sb_moves)
            gaps = [m["smartbot_rating_gap"] for m in sb_moves]
            s.smartbot_avg_rating_gap = mean(gaps)
            s.smartbot_median_rating_gap = median(gaps)
            # P90: 90th percentile of rating gap (worst 10%)
            if len(gaps) >= 4:
                s.smartbot_p90_rating_gap = quantiles(gaps, n=10)[-1]
            else:
                s.smartbot_p90_rating_gap = max(gaps) if gaps else 0.0

            s.smartbot_rank_1_rate = sum(
                1 for m in sb_moves if m.get("smartbot_llm_rank") == 1
            ) / nsb
            s.smartbot_top3_rate = sum(
                1 for m in sb_moves if m.get("smartbot_llm_rank", 99) <= 3
            ) / nsb

            # Category distribution
            cats = [m.get("smartbot_move_category", "") for m in sb_moves]
            for cat in ("brilliant", "good", "inaccuracy", "mistake", "blunder"):
                rate = sum(1 for c in cats if c == cat) / nsb
                setattr(s, f"smartbot_cat_{cat}", rate)
            s.smartbot_blunder_rate = s.smartbot_cat_blunder
            s.smartbot_brilliant_rate = s.smartbot_cat_brilliant

            # Threat & mate metrics
            threat_moves = [
                m for m in sb_moves if m.get("smartbot_threats_critical", 0) > 0
            ]
            if threat_moves:
                s.smartbot_threat_addressed_rate = sum(
                    1 for m in threat_moves if m.get("smartbot_threat_addressed")
                ) / len(threat_moves)
            s.smartbot_allows_mate_rate = sum(
                1 for m in sb_moves if m.get("smartbot_allows_mate")
            ) / nsb
            s.smartbot_missed_mate_count = sum(
                1 for m in sb_moves if m.get("smartbot_missed_mate")
            )

            # Component averages
            s.smartbot_avg_material = mean(
                m.get("smartbot_material", 0) for m in sb_moves
            )
            s.smartbot_avg_defense = mean(
                m.get("smartbot_defense", 0) for m in sb_moves
            )
            s.smartbot_avg_tactical = mean(
                m.get("smartbot_tactical", 0) for m in sb_moves
            )
            s.smartbot_avg_positional = mean(
                m.get("smartbot_positional", 0) for m in sb_moves
            )
            s.smartbot_avg_risk = mean(
                m.get("smartbot_risk", 0) for m in sb_moves
            )

        stats_list.append(s)

    return stats_list


def compute_composite_scores(stats_list: list[ModelStats]) -> list[ModelStats]:
    """Вычисляет composite score и ранжирует модели."""
    if not stats_list:
        return stats_list

    # Вычисляем raw scores
    for s in stats_list:
        s.reliability_score = (
            s.success_rate
            * (1 - s.retry_rate * 0.5)
            * (s.first_attempt_rate ** 0.5)
        )
        s.activity_score = s.avg_buried_delta  # будет нормализован
        s.tactical_score = (
            s.check_rate * 2 + s.capture_rate * 1.5 + s.avg_material_delta * 0.5
        )
        # Efficiency: инверсия стоимости (дешевле = лучше)
        s.efficiency_score = s.avg_cost_per_move  # будет нормализован

    # Нормализация в [0, 1]
    _normalize_field(stats_list, "activity_score")
    _normalize_field(stats_list, "tactical_score")
    _normalize_field_inverted(stats_list, "efficiency_score")
    # reliability_score уже в [0, 1]

    # SmartBot quality score (normalized from median_rating_gap)
    has_smartbot = any(s.smartbot_median_rating_gap > 0 for s in stats_list)
    if has_smartbot:
        # Compute quality_score via inverted normalization of median gap
        # (lower gap = better quality = higher score)
        gaps = [s.smartbot_median_rating_gap for s in stats_list]
        lo, hi = min(gaps), max(gaps)
        spread = hi - lo
        for s in stats_list:
            if spread == 0:
                s.smartbot_quality_score = 0.5
            else:
                s.smartbot_quality_score = 1.0 - (s.smartbot_median_rating_gap - lo) / spread

    # Composite
    for s in stats_list:
        if has_smartbot and s.smartbot_quality_score > 0:
            # Enhanced composite with SmartBot
            s.auto_composite = (
                0.20 * s.reliability_score
                + 0.35 * s.smartbot_quality_score
                + 0.15 * s.tactical_score
                + 0.10 * s.efficiency_score
                + 0.20 * s.win_rate  # win_rate уже в [0, 1]
            )
        else:
            # Legacy composite without SmartBot
            s.auto_composite = (
                0.35 * s.reliability_score
                + 0.30 * s.activity_score
                + 0.20 * s.tactical_score
                + 0.15 * s.efficiency_score
            )

    # Ранжирование
    stats_list.sort(key=lambda x: x.auto_composite, reverse=True)
    for i, s in enumerate(stats_list, 1):
        s.rank = i

    return stats_list


def _normalize_field(items: list[ModelStats], field_name: str) -> None:
    """Нормализует поле в [0, 1] по min-max."""
    values = [getattr(s, field_name) for s in items]
    lo, hi = min(values), max(values)
    spread = hi - lo
    if spread == 0:
        for s in items:
            setattr(s, field_name, 0.5)
        return
    for s in items:
        v = getattr(s, field_name)
        setattr(s, field_name, (v - lo) / spread)


def _normalize_field_inverted(
    items: list[ModelStats], field_name: str,
) -> None:
    """Нормализует поле в [0, 1] инвертированно (меньше = лучше)."""
    values = [getattr(s, field_name) for s in items]
    lo, hi = min(values), max(values)
    spread = hi - lo
    if spread == 0:
        for s in items:
            setattr(s, field_name, 0.5)
        return
    for s in items:
        v = getattr(s, field_name)
        setattr(s, field_name, 1.0 - (v - lo) / spread)
