"""Tab 3 — Thinking Gallery (v3 — поиск + подсветка + улучшения)."""
from __future__ import annotations

import json
from typing import Any, Callable

from nicegui import ui

from export_utils import moves_to_markdown


def create_thinking_gallery(
    traces: list[dict],
    game_filter: Callable[[], str],
    on_select_move: Callable[[dict], None],
) -> dict[str, Any]:
    """Строит вкладку Thinking Gallery."""

    selected_indices: set[int] = set()

    # ── Фильтры ──
    with ui.row().classes("w-full gap-2 items-end mb-2 flex-wrap"):
        filter_model = ui.select(
            label="Модель",
            options=["All"] + sorted(set(t["model"] for t in traces)),
            value="All",
            on_change=lambda _: _rebuild(),
        ).classes("w-48")

        filter_outcome = ui.select(
            label="Outcome",
            options=["All"] + sorted(set(t["outcome"] for t in traces)),
            value="All",
            on_change=lambda _: _rebuild(),
        ).classes("w-36")

        filter_length = ui.select(
            label="Длина thinking",
            options={
                "all": "Все",
                "short": "Короткие (< 200)",
                "medium": "Средние (200-500)",
                "long": "Длинные (> 500)",
            },
            value="all",
            on_change=lambda _: _rebuild(),
        ).classes("w-44")

        sort_by = ui.select(
            label="Сортировка",
            options={
                "move": "По номеру хода",
                "time": "По времени LLM (↓)",
                "length": "По длине thinking (↓)",
                "tokens": "По токенам (↓)",
                "cost": "По стоимости (↓)",
            },
            value="move",
            on_change=lambda _: _rebuild(),
        ).classes("w-48")

        # ✨ ЭТАП 3: Поиск по тексту thinking
        search_input = ui.input(
            label="🔍 Поиск в thinking",
            placeholder="Текст для поиска...",
            on_change=lambda _: _rebuild(),
        ).classes("w-56").props("clearable dense")

        ui.space()
        count_label = ui.label("").classes("text-sm text-gray-500")

    # ── Панель мультиселекта ──
    with ui.row().classes("w-full gap-2 items-center mb-2"):
        ui.button(
            "Выбрать все",
            icon="select_all",
            on_click=lambda: _select_all(),
        ).props("flat dense size=sm")

        ui.button(
            "Снять выбор",
            icon="deselect",
            on_click=lambda: _deselect_all(),
        ).props("flat dense size=sm")

        ui.space()

        selected_label = ui.label("Выбрано: 0").classes(
            "text-sm text-gray-500"
        )

        ui.button(
            "Copy MD",
            icon="content_copy",
            on_click=lambda: _copy_selected_md(),
        ).props("flat dense size=sm color=primary").tooltip(
            "Copy selected as Markdown"
        )

        ui.button(
            "Copy JSON",
            icon="data_object",
            on_click=lambda: _copy_selected_json(),
        ).props("flat dense size=sm").tooltip(
            "Copy selected as JSON"
        )

    # ── Контейнер ──
    cards_container = ui.column().classes("w-full gap-2")

    _filtered: list[tuple[int, dict]] = []
    _checkboxes: list[ui.checkbox] = []

    def _get_filtered() -> list[tuple[int, dict]]:
        gf = game_filter()
        search_lower = (
            (search_input.value or "").strip().lower()
        )
        result = []
        for i, t in enumerate(traces):
            if gf and gf != "__all__" and t["game_id"] != gf:
                continue
            if (
                filter_model.value
                and filter_model.value != "All"
                and t["model"] != filter_model.value
            ):
                continue
            if (
                filter_outcome.value
                and filter_outcome.value != "All"
                and t["outcome"] != filter_outcome.value
            ):
                continue
            tl = t.get("thinking_length", 0)
            fl = filter_length.value
            if fl == "short" and tl >= 200:
                continue
            if fl == "medium" and (tl < 200 or tl > 500):
                continue
            if fl == "long" and tl <= 500:
                continue
            # ✨ ЭТАП 3: текстовый поиск
            if search_lower:
                thinking_text = (t.get("thinking") or "").lower()
                if search_lower not in thinking_text:
                    continue
            result.append((i, t))

        sb = sort_by.value
        if sb == "time":
            result.sort(key=lambda x: x[1]["llm_time"], reverse=True)
        elif sb == "length":
            result.sort(
                key=lambda x: x[1]["thinking_length"], reverse=True
            )
        elif sb == "tokens":
            result.sort(
                key=lambda x: x[1]["total_tokens"], reverse=True
            )
        elif sb == "cost":
            result.sort(
                key=lambda x: x[1]["cost_usd"], reverse=True
            )
        else:
            result.sort(
                key=lambda x: (x[1]["game_id"], x[1]["move_number"])
            )
        return result

    def _rebuild() -> None:
        nonlocal _filtered, _checkboxes
        selected_indices.clear()
        _checkboxes.clear()
        cards_container.clear()
        _filtered = _get_filtered()
        count_label.set_text(f"Показано: {len(_filtered)} ходов")
        _update_selected_label()

        with cards_container:
            if not _filtered:
                with ui.column().classes("w-full items-center p-8"):
                    ui.icon("search_off", size="lg").classes(
                        "text-gray-300"
                    )
                    ui.label("Ничего не найдено").classes(
                        "text-gray-400 mt-2"
                    )
                return

            for idx, (orig_i, t) in enumerate(_filtered):
                _render_card(idx, orig_i, t)

    def _shorten_model(model: str) -> str:
        if "/" in model:
            return model.split("/")[-1]
        return model if len(model) <= 20 else model[:18] + "…"

    def _render_card(idx: int, orig_i: int, t: dict) -> None:
        thinking = t.get("thinking", "")
        outcome = t["outcome"]
        if outcome == "success":
            outcome_color = "green"
        elif outcome.startswith("fallback_random"):
            outcome_color = "orange"
        else:
            outcome_color = "red"

        move_str = (
            f"{t['move_from']}→{t['move_to']}"
            if t["move_from"]
            else "—"
        )

        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center gap-2"):
                cb = ui.checkbox(
                    value=False,
                    on_change=lambda e, _i=idx: _toggle_select(
                        _i, e.value
                    ),
                )
                _checkboxes.append(cb)

                ui.label(
                    f"#{t['move_number']}"
                ).classes("font-bold text-sm")

                ui.badge(
                    t["game_id_short"], color="blue"
                ).props("outline").classes("text-xs")
                ui.badge(
                    _shorten_model(t["model"]), color="indigo"
                ).props("outline").classes("text-xs")
                ui.badge(
                    outcome, color=outcome_color
                ).classes("text-xs")

                # ✨ ЭТАП 3: Ход как отдельный badge
                if move_str != "—":
                    ui.badge(
                        f"🎯 {move_str}", color="grey-7"
                    ).props("outline").classes("text-xs font-mono")

                ui.space()

                # ✨ ЭТАП 3: компактные метрики
                ui.label(
                    f"{t['llm_time']:.1f}s · "
                    f"{t['total_tokens']} tok · "
                    f"${t['cost_usd']:.5f} · "
                    f"{t['thinking_length']} ch"
                ).classes("text-xs text-gray-400 font-mono")

                if t.get("retries", 0) > 0:
                    ui.badge(
                        f"{t['retries']}x retry", color="orange"
                    ).classes("text-xs")

                ui.button(
                    icon="visibility",
                    on_click=lambda _t=t: on_select_move(_t),
                ).props(
                    "flat dense round size=sm"
                ).tooltip("Move Detail")

            if thinking:
                ui.textarea(value=thinking).classes(
                    "w-full font-mono text-xs"
                ).props("readonly outlined autogrow").style(
                    "max-height: 250px; overflow-y: auto;"
                )
            else:
                ui.label("(пустой thinking)").classes(
                    "text-xs text-gray-400 italic"
                )

    def _toggle_select(idx: int, checked: bool) -> None:
        if checked:
            selected_indices.add(idx)
        else:
            selected_indices.discard(idx)
        _update_selected_label()

    def _select_all() -> None:
        selected_indices.clear()
        for i, cb in enumerate(_checkboxes):
            cb.value = True
            selected_indices.add(i)
        _update_selected_label()

    def _deselect_all() -> None:
        selected_indices.clear()
        for cb in _checkboxes:
            cb.value = False
        _update_selected_label()

    def _update_selected_label() -> None:
        selected_label.set_text(f"Выбрано: {len(selected_indices)}")

    def _get_selected_traces() -> list[dict]:
        return [
            _filtered[idx][1]
            for idx in sorted(selected_indices)
            if idx < len(_filtered)
        ]

    def _copy_selected_md() -> None:
        sel = _get_selected_traces()
        if not sel:
            ui.notify("Ничего не выбрано", type="warning")
            return
        text = moves_to_markdown(sel)
        ui.run_javascript(
            f"navigator.clipboard.writeText({json.dumps(text)})"
        )
        ui.notify(
            f"MD: {len(sel)} ходов", type="positive", timeout=2000
        )

    def _copy_selected_json() -> None:
        sel = _get_selected_traces()
        if not sel:
            ui.notify("Ничего не выбрано", type="warning")
            return
        export = [
            {k: v for k, v in t.items() if k != "raw_trace"}
            for t in sel
        ]
        text = json.dumps(
            export, indent=2, ensure_ascii=False, default=str
        )
        ui.run_javascript(
            f"navigator.clipboard.writeText({json.dumps(text)})"
        )
        ui.notify(
            f"JSON: {len(sel)} ходов", type="positive", timeout=2000
        )

    def refresh(game_id: str) -> None:
        _rebuild()

    _rebuild()
    return {"refresh": refresh}
