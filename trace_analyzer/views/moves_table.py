"""Tab 2 — Таблица ходов: сортировка, фильтрация, цветные badges, поиск."""
from __future__ import annotations

from typing import Any, Callable

from nicegui import ui


def create_moves_table(
    traces: list[dict],
    on_select_move: Callable[[dict], None],
    game_filter: Callable[[], str],
) -> dict[str, Any]:
    """Строит вкладку с таблицей ходов."""

    columns = [
        {
            "name": "game",
            "label": "Game",
            "field": "game_id_short",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "move",
            "label": "#",
            "field": "move_number",
            "sortable": True,
        },
        {
            "name": "model",
            "label": "Model",
            "field": "model_short",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "outcome",
            "label": "Outcome",
            "field": "outcome",
            "sortable": True,
            "align": "center",
        },
        {
            "name": "llm_time",
            "label": "LLM Time",
            "field": "llm_time_raw",
            "sortable": True,
            "align": "right",
            # ✨ ЭТАП 3: для корректной сортировки используем числовое поле
        },
        {
            "name": "tokens",
            "label": "Tokens",
            "field": "total_tokens",
            "sortable": True,
            "align": "right",
        },
        {
            "name": "cost",
            "label": "Cost $",
            "field": "cost_raw",
            "sortable": True,
            "align": "right",
        },
        {
            "name": "retries",
            "label": "Ret.",
            "field": "retries",
            "sortable": True,
            "align": "center",
        },
        {
            "name": "thinking_preview",
            "label": "Thinking",
            "field": "thinking_preview",
            "sortable": False,
            "align": "left",
            "classes": "max-w-xs truncate",
        },
    ]

    def _shorten_model(model: str) -> str:
        """openai/gpt-4.1-mini → gpt-4.1-mini"""
        if "/" in model:
            return model.split("/")[-1]
        return model if len(model) <= 24 else model[:22] + "…"

    def _make_rows(
        filter_game: str,
        filter_outcome: str,
        filter_model: str,
        search_text: str,
    ) -> list[dict]:
        rows = []
        search_lower = search_text.strip().lower() if search_text else ""

        for i, t in enumerate(traces):
            # Фильтр по игре
            if filter_game and filter_game != "__all__":
                if t["game_id"] != filter_game:
                    continue
            # Фильтр по outcome
            if filter_outcome and filter_outcome != "All":
                if t["outcome"] != filter_outcome:
                    continue
            # Фильтр по модели
            if filter_model and filter_model != "All":
                if t["model"] != filter_model:
                    continue
            # ✨ ЭТАП 3: Поиск по тексту thinking
            if search_lower:
                thinking = (t.get("thinking") or "").lower()
                if search_lower not in thinking:
                    continue

            thinking = t.get("thinking", "")
            preview = thinking[:80].replace("\n", " ")
            if len(thinking) > 80:
                preview += "…"

            rows.append(
                {
                    "id": i,
                    "game_id_short": t["game_id_short"],
                    "move_number": t["move_number"],
                    "model_short": _shorten_model(t["model"]),
                    "outcome": t["outcome"],
                    "llm_time_raw": round(t["llm_time"], 3),
                    "total_tokens": t["total_tokens"],
                    "cost_raw": round(t["cost_usd"], 6),
                    "retries": t["retries"],
                    "thinking_preview": preview,
                }
            )
        return rows

    # ── Фильтры ──
    with ui.row().classes("w-full gap-2 items-end mb-2 flex-wrap"):
        outcome_filter = ui.select(
            label="Outcome",
            options=["All"] + sorted(set(t["outcome"] for t in traces)),
            value="All",
            on_change=lambda _: _apply_filters(),
        ).classes("w-36")

        model_filter = ui.select(
            label="Model",
            options=["All"] + sorted(set(t["model"] for t in traces)),
            value="All",
            on_change=lambda _: _apply_filters(),
        ).classes("w-52")

        # ✨ ЭТАП 3: Поиск по тексту thinking
        search_input = ui.input(
            label="🔍 Поиск в thinking",
            placeholder="Введите текст для поиска...",
            on_change=lambda _: _apply_filters(),
        ).classes("w-64").props("clearable dense")

        ui.space()
        count_label = ui.label("").classes("text-sm text-gray-500")

    # ── Таблица ──
    initial_rows = _make_rows("__all__", "All", "All", "")

    table = ui.table(
        columns=columns,
        rows=initial_rows,
        row_key="id",
        pagination={"rowsPerPage": 50, "sortBy": "move", "descending": False},
    ).classes("w-full").props("dense flat bordered")

    # ✨ ЭТАП 3: Цветные badges для outcome через Quasar slot
    table.add_slot(
        "body-cell-outcome",
        '''
        <q-td :props="props">
            <q-badge
                :color="props.value === 'success' ? 'green'
                      : props.value === 'fallback_random' ? 'orange'
                      : 'red'"
                :label="props.value"
                outline
            />
        </q-td>
        ''',
    )

    # ✨ ЭТАП 3: Цвет для времени — подсветка медленных ходов
    table.add_slot(
        "body-cell-llm_time",
        '''
        <q-td :props="props">
            <span
                :class="props.value > 10 ? 'text-red-600 font-bold'
                      : props.value > 5 ? 'text-orange-600 font-bold'
                      : 'text-gray-700'"
            >
                {{ props.value.toFixed(2) }}s
            </span>
        </q-td>
        ''',
    )

    # ✨ ЭТАП 3: Цвет для cost
    table.add_slot(
        "body-cell-cost",
        '''
        <q-td :props="props">
            <span class="font-mono text-xs">
                ${{ props.value.toFixed(6) }}
            </span>
        </q-td>
        ''',
    )

    # ✨ ЭТАП 3: Цветной badge для ретраев
    table.add_slot(
        "body-cell-retries",
        '''
        <q-td :props="props">
            <q-badge
                v-if="props.value > 0"
                :color="props.value >= 2 ? 'red' : 'orange'"
                :label="props.value + 'x'"
            />
            <span v-else class="text-gray-300">—</span>
        </q-td>
        ''',
    )

    # Клик по строке
    table.on("rowClick", lambda e: _on_row_click(e))
    count_label.set_text(f"Показано: {len(initial_rows)} ходов")

    def _on_row_click(e: Any) -> None:
        try:
            row = e.args[1]
            idx = row.get("id", 0)
            if 0 <= idx < len(traces):
                on_select_move(traces[idx])
        except (IndexError, KeyError, TypeError):
            pass

    def _apply_filters() -> None:
        gf = game_filter()
        rows = _make_rows(
            gf,
            outcome_filter.value or "All",
            model_filter.value or "All",
            search_input.value or "",
        )
        table.rows = rows
        table.update()
        count_label.set_text(f"Показано: {len(rows)} ходов")

    def refresh(game_id: str) -> None:
        _apply_filters()

    return {"table": table, "refresh": refresh}
