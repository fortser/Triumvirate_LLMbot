"""Tab 1 — Overview (v3 — доп. графики, улучшения)."""
from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from data_loader import get_games_summary


def create_overview(
    traces: list[dict],
    game_filter: Callable[[], str],
) -> dict[str, Any]:
    """Строит вкладку Overview."""

    summaries = get_games_summary(traces)

    # ── Общая сводка ──
    total_cost = sum(t["cost_usd"] for t in traces)
    total_tokens = sum(t["total_tokens"] for t in traces)
    avg_time = (
        sum(t["llm_time"] for t in traces) / len(traces)
        if traces
        else 0
    )
    total_retries = sum(t["retries"] for t in traces)

    with ui.row().classes("w-full gap-3 flex-wrap mb-3"):
        _summary_card("🎮 Игр", str(len(summaries)), "blue")
        _summary_card("♟ Ходов", str(len(traces)), "indigo")
        _summary_card("💰 Общая стоимость", f"${total_cost:.4f}", "green")
        _summary_card("🔢 Всего токенов", f"{total_tokens:,}", "purple")
        _summary_card("⏱ Ср. время LLM", f"{avg_time:.2f}s", "orange")
        _summary_card(
            "🔄 Ретраи", str(total_retries),
            "green" if total_retries == 0 else "red",
        )

    # ── Карточки по каждой игре ──
    ui.label("📋 Игры").classes("text-lg font-bold mt-1 mb-1")

    with ui.row().classes("w-full gap-3 flex-wrap"):
        for gs in summaries:
            with ui.card().classes("min-w-72"):
                with ui.row().classes("items-center gap-2 mb-1"):
                    ui.label(f"🎮 {gs['game_id_short']}…").classes(
                        "font-bold text-sm"
                    )
                    ui.badge(
                        _shorten(gs["model"]), color="blue"
                    ).props("outline").classes("text-xs")

                with ui.element("div").classes(
                    "grid grid-cols-2 gap-x-4 gap-y-1 text-xs"
                ):
                    _metric("Ходов", str(gs["total_moves"]))
                    _metric(
                        "Стоимость", f"${gs['total_cost']:.6f}"
                    )
                    _metric(
                        "Ср. $/ход", f"${gs['avg_cost']:.6f}"
                    )
                    _metric(
                        "Ср. время", f"{gs['avg_time']:.2f}s"
                    )
                    _metric(
                        "Медиана", f"{gs['median_time']:.2f}s"
                    )
                    _metric(
                        "Макс.", f"{gs['max_time']:.2f}s"
                    )
                    _metric(
                        "Ср. токенов", f"{gs['avg_tokens']:.0f}"
                    )
                    _metric(
                        "Всего ток.", f"{gs['total_tokens']:,}"
                    )
                    _metric(
                        "Success",
                        f"{gs['success_rate']:.0f}%",
                        color="green"
                        if gs["success_rate"] > 90
                        else "orange",
                    )
                    _metric(
                        "Retry",
                        f"{gs['retry_rate']:.0f}%",
                        color="green"
                        if gs["retry_rate"] < 10
                        else "orange",
                    )
                    _metric(
                        "Fallback",
                        f"{gs['fallback_rate']:.0f}%",
                        color="green"
                        if gs["fallback_rate"] == 0
                        else "red",
                    )

    # ── Сравнение моделей ──
    models_data = _aggregate_by_model(traces)
    if len(models_data) >= 1:
        ui.separator().classes("my-3")
        ui.label("📊 Сравнение моделей").classes(
            "text-lg font-bold mb-1"
        )
        model_columns = [
            {"name": "model", "label": "Model", "field": "model",
             "align": "left", "sortable": True},
            {"name": "games", "label": "Games", "field": "games",
             "sortable": True},
            {"name": "moves", "label": "Moves", "field": "moves",
             "sortable": True},
            {"name": "avg_time", "label": "Avg Time",
             "field": "avg_time", "sortable": True},
            {"name": "avg_tokens", "label": "Avg Tokens",
             "field": "avg_tokens", "sortable": True},
            {"name": "avg_cost", "label": "Avg Cost",
             "field": "avg_cost", "sortable": True},
            {"name": "total_cost", "label": "Total Cost",
             "field": "total_cost", "sortable": True},
            {"name": "success_pct", "label": "Success%",
             "field": "success_pct", "sortable": True},
            {"name": "retry_pct", "label": "Retry%",
             "field": "retry_pct", "sortable": True},
        ]
        model_rows = [
            {
                "model": md["model"],
                "games": md["games"],
                "moves": md["moves"],
                "avg_time": f"{md['avg_time']:.2f}s",
                "avg_tokens": f"{md['avg_tokens']:.0f}",
                "avg_cost": f"${md['avg_cost']:.6f}",
                "total_cost": f"${md['total_cost']:.6f}",
                "success_pct": f"{md['success_pct']:.0f}%",
                "retry_pct": f"{md['retry_pct']:.0f}%",
            }
            for md in models_data
        ]
        ui.table(
            columns=model_columns,
            rows=model_rows,
            row_key="model",
        ).classes("w-full").props("dense flat bordered")

    # ── Графики ──
    ui.separator().classes("my-3")
    ui.label("📈 Графики").classes("text-lg font-bold mb-1")

    with ui.row().classes("w-full gap-4"):
        # ✨ ЭТАП 3: Scatter-plot — LLM Time
        with ui.column().classes("flex-1"):
            ui.label("⏱ LLM Time по ходам").classes(
                "text-sm font-bold text-gray-600"
            )
            chart_time = _build_scatter_data(
                traces, "llm_time", "LLM Time (sec)"
            )
            ui.echart(chart_time).classes("w-full").style(
                "height: 300px;"
            )

        # ✨ ЭТАП 3: Scatter-plot — Tokens
        with ui.column().classes("flex-1"):
            ui.label("🔢 Tokens по ходам").classes(
                "text-sm font-bold text-gray-600"
            )
            chart_tokens = _build_scatter_data(
                traces, "total_tokens", "Total Tokens"
            )
            ui.echart(chart_tokens).classes("w-full").style(
                "height: 300px;"
            )

    # ✨ ЭТАП 3: Bar-chart — стоимость по ходам (если есть cost > 0)
    if total_cost > 0:
        with ui.row().classes("w-full gap-4 mt-2"):
            with ui.column().classes("flex-1"):
                ui.label("💰 Cost по ходам").classes(
                    "text-sm font-bold text-gray-600"
                )
                chart_cost = _build_scatter_data(
                    traces, "cost_usd", "Cost (USD)"
                )
                ui.echart(chart_cost).classes("w-full").style(
                    "height: 250px;"
                )

    # ── Аномалии ──
    ui.separator().classes("my-3")
    ui.label("⚠️ Аномалии").classes("text-lg font-bold mb-1")
    _show_anomalies(traces)

    return {}


def _summary_card(
    label: str, value: str, color: str
) -> None:
    """Компактная карточка сводной метрики."""
    with ui.card().classes("min-w-36"):
        ui.label(label).classes("text-xs text-gray-500")
        ui.label(value).classes(
            f"text-lg font-bold text-{color}-600"
        )


def _shorten(model: str) -> str:
    if "/" in model:
        return model.split("/")[-1]
    return model if len(model) <= 20 else model[:18] + "…"


def _metric(
    label: str, value: str, color: str | None = None
) -> None:
    ui.label(label).classes("text-gray-500")
    cls = "font-mono font-bold"
    if color:
        cls += f" text-{color}-600"
    ui.label(value).classes(cls)


def _aggregate_by_model(traces: list[dict]) -> list[dict]:
    by_model: dict[str, list[dict]] = {}
    for t in traces:
        by_model.setdefault(t["model"], []).append(t)

    result = []
    for model, moves in sorted(by_model.items()):
        times = [m["llm_time"] for m in moves if m["llm_time"] > 0]
        costs = [m["cost_usd"] for m in moves]
        tokens = [m["total_tokens"] for m in moves]
        game_ids = set(m["game_id"] for m in moves)
        success_count = sum(
            1 for m in moves if m["outcome"] == "success"
        )
        retry_count = sum(1 for m in moves if m["retries"] > 0)
        result.append(
            {
                "model": model,
                "games": len(game_ids),
                "moves": len(moves),
                "avg_time": sum(times) / len(times) if times else 0,
                "avg_tokens": (
                    sum(tokens) / len(tokens) if tokens else 0
                ),
                "avg_cost": sum(costs) / len(costs) if costs else 0,
                "total_cost": sum(costs),
                "success_pct": (
                    success_count / len(moves) * 100 if moves else 0
                ),
                "retry_pct": (
                    retry_count / len(moves) * 100 if moves else 0
                ),
            }
        )
    return result


def _build_scatter_data(
    traces: list[dict], field: str, y_label: str
) -> dict:
    """Конфигурация ECharts scatter-plot для произвольного числового поля."""
    series_map: dict[str, list] = {}
    for t in traces:
        key = f"{t['game_id_short']} ({_shorten(t['model'])})"
        series_map.setdefault(key, []).append(
            [t["move_number"], round(t[field], 4), t["outcome"]]
        )
    series = [
        {
            "name": name,
            "type": "scatter",
            "data": pts,
            "symbolSize": 8,
        }
        for name, pts in series_map.items()
    ]
    return {
        "tooltip": {
            "trigger": "item",
            "formatter": ":js:function(p){return "
            "'<b>'+p.seriesName+'</b><br/>"
            "Move #'+p.data[0]+'<br/>"
            + y_label
            + ": '+p.data[1]+'<br/>"
            "Outcome: '+p.data[2]}",
        },
        "legend": {"data": list(series_map.keys()), "top": 0},
        "grid": {"top": 40, "bottom": 30, "left": 60, "right": 20},
        "xAxis": {
            "name": "Move #",
            "type": "value",
            "nameLocation": "middle",
            "nameGap": 20,
        },
        "yAxis": {
            "name": y_label,
            "type": "value",
            "nameLocation": "middle",
            "nameGap": 45,
        },
        "series": series,
    }


def _show_anomalies(traces: list[dict]) -> None:
    if not traces:
        ui.label("Нет данных").classes("text-gray-400")
        return

    by_time = sorted(
        traces, key=lambda t: t["llm_time"], reverse=True
    )
    slow = by_time[:5]
    retried = [t for t in traces if t["retries"] > 0]
    errors = [
        t
        for t in traces
        if t["outcome"] not in ("success", "fallback_random")
    ]

    with ui.row().classes("w-full gap-4"):
        with ui.column().classes("flex-1"):
            ui.label("🐌 Самые медленные").classes(
                "font-bold text-sm text-gray-600 mb-1"
            )
            for t in slow:
                with ui.row().classes("text-xs gap-2 items-center"):
                    color = (
                        "red"
                        if t["llm_time"] > 10
                        else "orange"
                        if t["llm_time"] > 5
                        else "grey-7"
                    )
                    ui.badge(
                        f"{t['llm_time']:.1f}s", color=color
                    )
                    ui.label(
                        f"{t['game_id_short']} #{t['move_number']} "
                        f"| {_shorten(t['model'])}"
                    )

        with ui.column().classes("flex-1"):
            ui.label(
                f"🔄 Ретраи ({len(retried)})"
            ).classes("font-bold text-sm text-gray-600 mb-1")
            if retried:
                for t in retried[:8]:
                    with ui.row().classes(
                        "text-xs gap-2 items-center"
                    ):
                        ui.badge(
                            f"{t['retries']}x", color="orange"
                        )
                        ui.label(
                            f"{t['game_id_short']} #{t['move_number']} "
                            f"| {t['outcome']}"
                        )
            else:
                ui.label("Нет").classes("text-xs text-green-600")

        with ui.column().classes("flex-1"):
            ui.label(
                f"❌ Ошибки ({len(errors)})"
            ).classes("font-bold text-sm text-gray-600 mb-1")
            if errors:
                for t in errors[:8]:
                    with ui.row().classes(
                        "text-xs gap-2 items-center"
                    ):
                        ui.badge(
                            t["outcome"], color="red"
                        ).props("outline")
                        ui.label(
                            f"{t['game_id_short']} #{t['move_number']}"
                        )
            else:
                ui.label("Нет").classes("text-xs text-green-600")
