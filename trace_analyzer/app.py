#!/usr/bin/env python3
"""Triumvirate Trace Analyzer — анализатор trace-логов.

Запуск:
    python app.py                    # web: http://localhost:8091
    python app.py --logs ../logs     # указать папку логов
    python app.py --port 9000        # другой порт
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Добавляем текущую директорию в path для импортов
sys.path.insert(0, str(Path(__file__).parent))

from nicegui import ui

from data_loader import get_games_summary, scan_traces
from views.move_detail import create_move_detail
from views.moves_table import create_moves_table
from views.overview import create_overview
from views.thinking_gallery import create_thinking_gallery


def create_app(logs_dir: str) -> None:
    """Построение GUI анализатора."""

    # ── Загрузка данных ──
    traces = scan_traces(logs_dir)
    games_summary = get_games_summary(traces)

    if not traces:
        with ui.column().classes("w-full items-center p-8"):
            ui.icon("folder_open", size="xl").classes("text-gray-300")
            ui.label(
                f"Trace-файлы не найдены в: {logs_dir}"
            ).classes("text-xl text-red-500 mt-4")
            ui.label(
                "Убедитесь, что папка logs/ содержит подпапки "
                "game_*/move_*.json"
            ).classes("text-gray-500")
            ui.label(
                "Запуск: python app.py --logs /path/to/logs"
            ).classes("text-sm text-gray-400 font-mono mt-2")
        return

    total_moves = len(traces)
    total_games = len(games_summary)
    models = sorted(set(t["model"] for t in traces))
    total_cost = sum(t["cost_usd"] for t in traces)

    # ── Состояние ──
    _state: dict = {"selected_game": "__all__", "selected_trace": None}

    # ── Header ──
    with ui.header(elevated=True).classes(
        "bg-indigo-800 text-white items-center px-4"
    ):
        ui.label("📊 Triumvirate Trace Analyzer").classes(
            "text-lg font-bold"
        )
        ui.space()
        ui.label(
            f"{total_games} игр | {total_moves} ходов | "
            f"${total_cost:.4f} | "
            f"Модели: {', '.join(models)}"
        ).classes("text-sm opacity-80")

    # ── Навигация: фильтр по игре ──
    with ui.row().classes("w-full px-4 pt-2 items-center gap-3"):
        game_options = {"__all__": f"Все игры ({total_games})"}
        for gs in games_summary:
            game_options[gs["game_id"]] = (
                f"{gs['game_id_short']}… | {gs['model']} | "
                f"{gs['total_moves']} ходов | "
                f"${gs['total_cost']:.4f}"
            )

        game_select = ui.select(
            label="Фильтр по игре",
            options=game_options,
            value="__all__",
            on_change=lambda e: _on_game_change(e.value),
        ).classes("w-96")

    # Словарь для хранения view-контроллеров
    _views: dict = {}

    def _on_game_change(game_id: str) -> None:
        _state["selected_game"] = game_id
        if "moves" in _views:
            _views["moves"]["refresh"](game_id)
        if "thinking" in _views:
            _views["thinking"]["refresh"](game_id)

    def _get_game_filter() -> str:
        return _state["selected_game"]

    # ── Tabs ──
    with ui.column().classes("w-full px-4 pb-4").style(
        "height: calc(100vh - 110px); overflow: hidden;"
    ):
        with ui.tabs().classes("w-full") as tabs:
            tab_overview = ui.tab("Overview", icon="dashboard")
            tab_moves = ui.tab("Moves", icon="list")
            tab_thinking = ui.tab("Thinking", icon="psychology")
            tab_detail = ui.tab("Move Detail", icon="visibility")

        with ui.tab_panels(tabs, value=tab_overview).classes(
            "w-full flex-1"
        ).style("overflow-y: auto;"):

            # ── Tab 1: Overview ──
            with ui.tab_panel(tab_overview):
                _views["overview"] = create_overview(
                    traces=traces,
                    game_filter=_get_game_filter,
                )

            # ── Tab 2: Moves ──
            with ui.tab_panel(tab_moves):
                def _on_select_move(trace: dict) -> None:
                    _state["selected_trace"] = trace
                    _views["detail"]["show_move"](trace)
                    tabs.set_value(tab_detail)

                _views["moves"] = create_moves_table(
                    traces=traces,
                    on_select_move=_on_select_move,
                    game_filter=_get_game_filter,
                )

            # ── Tab 3: Thinking Gallery ──
            with ui.tab_panel(tab_thinking):
                def _on_thinking_select(trace: dict) -> None:
                    _state["selected_trace"] = trace
                    _views["detail"]["show_move"](trace)
                    tabs.set_value(tab_detail)

                _views["thinking"] = create_thinking_gallery(
                    traces=traces,
                    game_filter=_get_game_filter,
                    on_select_move=_on_thinking_select,
                )

            # ── Tab 4: Move Detail ──
            with ui.tab_panel(tab_detail):
                def _on_navigate(trace: dict) -> None:
                    _state["selected_trace"] = trace
                    _views["detail"]["show_move"](trace)

                _views["detail"] = create_move_detail(
                    traces=traces,
                    get_current_trace=lambda: _state["selected_trace"],
                    on_navigate=_on_navigate,
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Triumvirate Trace Analyzer"
    )
    parser.add_argument(
        "--logs",
        default=None,
        help="Путь к папке logs/ (по умолчанию: ../logs рядом со скриптом)",
    )
    parser.add_argument(
        "--port", type=int, default=8091, help="Порт (default: 8091)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host")
    args = parser.parse_args()

    # Определяем путь к логам
    if args.logs:
        logs_dir = args.logs
    else:
        script_dir = Path(__file__).parent
        logs_dir = str(script_dir.parent / "logs")
        if not Path(logs_dir).exists():
            logs_dir = str(Path.cwd() / "logs")

    print(f"📂 Logs directory: {logs_dir}")
    print(f"🌐 Starting on http://localhost:{args.port}")

    create_app(logs_dir)

    ui.run(
        host=args.host,
        port=args.port,
        title="Triumvirate Trace Analyzer",
        reload=False,
        show=True,
    )


if __name__ == "__main__":
    main()
