"""CLI entry point для вычисления автоматических метрик.

Использование:
    python -m trace_analyzer.metrics
    python -m trace_analyzer.metrics --model "openai/gpt-4.1-mini"
    python -m trace_analyzer.metrics --stdout --format table
    python -m trace_analyzer.metrics --logs-dir ./other_logs/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Добавляем корень проекта в path (для notation_converter)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from trace_analyzer.aggregator import (
    GameResult,
    ModelStats,
    aggregate_by_game,
    aggregate_by_model,
    compute_composite_scores,
)
from trace_analyzer.data_loader import scan_traces
from trace_analyzer.move_metrics import MoveMetrics, compute_move_metrics


def run(
    logs_dir: Path,
    output_dir: Path,
    *,
    model_filter: str | None = None,
    game_filter: str | None = None,
    stdout: bool = False,
    fmt: str = "table",
    smartbot: bool = False,
    smartbot_path: str | None = None,
    check_mates: bool = False,
) -> dict:
    """Главная функция: загрузка → метрики → агрегация → сохранение."""
    t0 = time.time()

    # SmartBot path override
    if smartbot_path:
        import os
        os.environ["SMARTBOT_PATH"] = smartbot_path

    # 1. Загрузка сырых трейсов
    raw_traces = _load_raw_traces(logs_dir)
    if not raw_traces:
        print(f"No traces found in {logs_dir}")
        return {}

    # 1.5 Pre-filter raw traces (before expensive SmartBot eval)
    if model_filter or game_filter:
        filtered = []
        for raw in raw_traces:
            if game_filter and game_filter not in raw.get("game_id", ""):
                continue
            if model_filter:
                state = raw.get("server_state_raw") or {}
                model = ""
                players = state.get("players") or []
                current = state.get("current_player", "")
                for p in players:
                    if p.get("color") == current and p.get("model"):
                        model = p["model"]
                        break
                if not model:
                    import re
                    src = raw.get("_source_file", "")
                    match = re.search(r"game_[^_]+__(.+?)[\\/]", src)
                    model = match.group(1).replace("_", "/", 1) if match else ""
                if model_filter not in model:
                    continue
            filtered.append(raw)
        raw_traces = filtered
        if not raw_traces:
            print("No traces match the filter criteria.")
            return {}

    # 2. SmartBot evaluation (optional)
    sb_results: dict[tuple[str, int], dict] = {}
    if smartbot:
        from trace_analyzer.smartbot_evaluator import evaluate_traces
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        print(f"Running SmartBot evaluation on {len(raw_traces)} traces...")
        sb_list = evaluate_traces(raw_traces, check_mates=check_mates)
        for sb in sb_list:
            key = (sb.get("game_id", ""), sb.get("move_number", 0))
            sb_results[key] = sb

    # 3. Вычисление per-move метрик
    move_metrics: list[dict] = []
    for raw in raw_traces:
        sb_eval = None
        if sb_results:
            key = (raw.get("game_id", ""), raw.get("move_number", 0))
            sb_eval = sb_results.get(key)
        mm = compute_move_metrics(raw, smartbot_eval=sb_eval)
        d = mm.to_dict()
        # Фильтрация
        if model_filter and model_filter not in d["model"]:
            continue
        if game_filter and game_filter not in d["game_id"]:
            continue
        move_metrics.append(d)

    if not move_metrics:
        print("No moves match the filter criteria.")
        return {}

    # 3. Агрегация
    game_results = aggregate_by_game(move_metrics)
    model_stats = aggregate_by_model(move_metrics, game_results)
    model_stats = compute_composite_scores(model_stats)

    elapsed = time.time() - t0

    # 4. Вывод
    result = {
        "total_traces": len(move_metrics),
        "total_games": len(game_results),
        "total_models": len(model_stats),
        "elapsed_sec": round(elapsed, 2),
        "move_metrics": move_metrics,
        "game_results": [g.to_dict() for g in game_results],
        "model_rankings": [s.to_dict() for s in model_stats],
    }

    if stdout:
        if fmt == "table":
            _print_table(model_stats, elapsed, len(move_metrics))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _save_results(output_dir, result)
        _print_table(model_stats, elapsed, len(move_metrics))

    return result


def _load_raw_traces(logs_dir: Path) -> list[dict]:
    """Загружает сырые JSON-трейсы (без нормализации data_loader)."""
    if not logs_dir.exists():
        return []
    raw: list[dict] = []
    for f in sorted(logs_dir.rglob("move_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_source_file"] = str(f)
            raw.append(data)
        except Exception:
            continue
    return raw


def _save_results(output_dir: Path, result: dict) -> None:
    """Сохраняет результаты в JSON-файлы."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # metrics.json — per-move (без raw_trace для компактности)
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(result["move_metrics"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # model_rankings.json
    rankings_path = output_dir / "model_rankings.json"
    rankings_path.write_text(
        json.dumps(result["model_rankings"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # game_results.json
    games_path = output_dir / "game_results.json"
    games_path.write_text(
        json.dumps(result["game_results"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Saved: {metrics_path}")
    print(f"Saved: {rankings_path}")
    print(f"Saved: {games_path}")


def _print_table(
    stats: list[ModelStats], elapsed: float, total_moves: int,
) -> None:
    """Выводит таблицу рейтинга в stdout."""
    has_sb = any(s.smartbot_quality_score > 0 for s in stats)

    if has_sb:
        w = 120
        print(f"\n{'='*w}")
        print(f"  Model Rankings  |  {total_moves} moves, {len(stats)} models  |  {elapsed:.1f}s  |  SmartBot: ON")
        print(f"{'='*w}")
        print(
            f"{'#':>3} {'Model':<38} {'Comp':>5} {'SB_Q':>5} {'Gap':>5} "
            f"{'Bri%':>5} {'Bln%':>5} {'Rel':>5} {'Tac':>5} "
            f"{'Win%':>5} {'Moves':>5}"
        )
        print(f"{'-'*w}")
        for s in stats:
            print(
                f"{s.rank:>3} {s.model:<38} {s.auto_composite:.3f} "
                f"{s.smartbot_quality_score:.3f} {s.smartbot_avg_rating_gap:>5.0f} "
                f"{s.smartbot_brilliant_rate * 100:>4.0f}% "
                f"{s.smartbot_blunder_rate * 100:>4.0f}% "
                f"{s.reliability_score:.3f} {s.tactical_score:.3f} "
                f"{s.win_rate * 100:>4.0f}% {s.total_moves:>5}"
            )
        print(f"{'='*w}\n")
    else:
        w = 90
        print(f"\n{'='*w}")
        print(f"  Model Rankings  |  {total_moves} moves, {len(stats)} models  |  {elapsed:.1f}s")
        print(f"{'='*w}")
        print(
            f"{'#':>3} {'Model':<42} {'Comp':>5} {'Rel':>5} {'Act':>5} "
            f"{'Tac':>5} {'Eff':>5} {'Win%':>5} {'Moves':>5}"
        )
        print(f"{'-'*w}")
        for s in stats:
            print(
                f"{s.rank:>3} {s.model:<42} {s.auto_composite:.3f} "
                f"{s.reliability_score:.3f} {s.activity_score:.3f} "
                f"{s.tactical_score:.3f} {s.efficiency_score:.3f} "
                f"{s.win_rate * 100:>4.0f}% {s.total_moves:>5}"
            )
        print(f"{'='*w}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute automatic metrics for LLM game traces.",
    )
    parser.add_argument(
        "--logs-dir",
        default=str(_PROJECT_ROOT / "logs"),
        help="Path to logs directory (default: ./logs/)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_PROJECT_ROOT / "logs" / "evaluations"),
        help="Path to output directory (default: ./logs/evaluations/)",
    )
    parser.add_argument("--model", default=None, help="Filter by model name")
    parser.add_argument("--game", default=None, help="Filter by game ID")
    parser.add_argument(
        "--stdout", action="store_true", help="Output to stdout instead of files",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for --stdout",
    )
    parser.add_argument(
        "--smartbot",
        action="store_true",
        help="Enable SmartBot evaluation for objective move quality metrics",
    )
    parser.add_argument(
        "--smartbot-path",
        default=None,
        help="Path to SmartBot project (overrides SMARTBOT_PATH env)",
    )
    parser.add_argument(
        "--check-mates",
        action="store_true",
        help="Enable mate threat checking (slow, requires --smartbot)",
    )

    args = parser.parse_args()
    run(
        logs_dir=Path(args.logs_dir),
        output_dir=Path(args.output_dir),
        model_filter=args.model,
        game_filter=args.game,
        stdout=args.stdout,
        fmt=args.format,
        smartbot=args.smartbot,
        smartbot_path=args.smartbot_path,
        check_mates=args.check_mates,
    )


if __name__ == "__main__":
    main()
