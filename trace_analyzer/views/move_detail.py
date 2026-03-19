"""Tab 4 — Детальный просмотр хода (v3 — цветной Parser, улучшенный UX)."""
from __future__ import annotations

import json
from typing import Any, Callable

from nicegui import ui

from export_utils import (
    format_llm_interaction_md,
    format_parser_md,
    format_prompt_pipeline_md,
    move_to_markdown,
    section_to_json,
)


def create_move_detail(
    traces: list[dict],
    get_current_trace: Callable[[], dict | None],
    on_navigate: Callable[[dict], None],
) -> dict[str, Any]:
    """Строит вкладку детализации хода."""

    container = ui.column().classes("w-full gap-2")
    _state: dict[str, Any] = {"current_idx": -1}

    def _copy(text: str, label: str = "Скопировано") -> None:
        ui.run_javascript(
            f"navigator.clipboard.writeText({json.dumps(text)})"
        )
        ui.notify(label, type="positive", timeout=1500)

    def _make_copy_btn(
        get_text: Callable[[], str], label: str = ""
    ) -> None:
        tip = f"Копировать {label}" if label else "Копировать"
        ui.button(
            icon="content_copy",
            on_click=lambda: _copy(get_text(), f"{label} скопировано"),
        ).props("flat dense round size=sm").tooltip(tip)

    def show_move(trace: dict | None) -> None:
        container.clear()

        if trace is None:
            with container:
                with ui.column().classes("w-full items-center p-12"):
                    ui.icon("visibility", size="xl").classes(
                        "text-gray-200"
                    )
                    ui.label(
                        "Выберите ход в таблице (Moves) "
                        "или галерее (Thinking)"
                    ).classes("text-gray-400 text-lg mt-4")
            return

        raw = trace.get("raw_trace", {})

        # Находим индекс
        idx = -1
        for i, t in enumerate(traces):
            if (
                t["game_id"] == trace["game_id"]
                and t["move_number"] == trace["move_number"]
            ):
                idx = i
                break
        _state["current_idx"] = idx

        with container:
            # ── Header ──
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center gap-3"):
                    # Prev/Next
                    prev_btn = ui.button(
                        icon="arrow_back",
                        on_click=lambda: _navigate(-1),
                    ).props("flat dense round")
                    if idx <= 0:
                        prev_btn.disable()

                    next_btn = ui.button(
                        icon="arrow_forward",
                        on_click=lambda: _navigate(1),
                    ).props("flat dense round")
                    if idx >= len(traces) - 1:
                        next_btn.disable()

                    # ✨ ЭТАП 3: навигационная метка
                    if idx >= 0:
                        ui.label(f"{idx + 1}/{len(traces)}").classes(
                            "text-xs text-gray-400"
                        )

                    ui.separator().props("vertical")

                    move_str = (
                        f"{trace['move_from']}→{trace['move_to']}"
                        if trace["move_from"]
                        else "—"
                    )
                    if trace.get("promotion"):
                        move_str += f" ={trace['promotion']}"

                    outcome = trace["outcome"]
                    if outcome == "success":
                        outcome_color = "green"
                    elif outcome.startswith("fallback_random"):
                        outcome_color = "orange"
                    else:
                        outcome_color = "red"

                    ui.label(
                        f"Game {trace['game_id_short']}"
                    ).classes("font-bold")
                    ui.label(
                        f"Move #{trace['move_number']}"
                    ).classes("text-lg font-bold")

                    ui.badge(outcome, color=outcome_color).props("outline")

                    ui.label(f"🎯 {move_str}").classes(
                        "text-sm font-mono bg-gray-100 px-2 py-1 rounded"
                    )

                    if trace.get("retries", 0) > 0:
                        ui.badge(
                            f"🔄 {trace['retries']} retries",
                            color="orange",
                        )

                    ui.space()

                    # ✨ ЭТАП 3: метрики в компактных badges
                    with ui.row().classes("gap-1"):
                        ui.badge(
                            f"⏱ {trace['llm_time']:.2f}s",
                            color="grey-7"
                            if trace["llm_time"] < 5
                            else "orange"
                            if trace["llm_time"] < 10
                            else "red",
                        ).props("outline")
                        ui.badge(
                            f"🔢 {trace['total_tokens']}",
                            color="grey-7",
                        ).props("outline")
                        ui.badge(
                            f"💰 ${trace['cost_usd']:.6f}",
                            color="grey-7",
                        ).props("outline")

                    ui.button(
                        "MD",
                        icon="content_copy",
                        on_click=lambda: _copy(
                            move_to_markdown(trace), "Markdown"
                        ),
                    ).props("flat dense size=sm").tooltip(
                        "Copy as Markdown"
                    )
                    ui.button(
                        "JSON",
                        icon="data_object",
                        on_click=lambda: _copy(
                            section_to_json(raw), "JSON"
                        ),
                    ).props("flat dense size=sm").tooltip(
                        "Copy full trace JSON"
                    )

            # ── 1. Thinking ──
            thinking = trace.get("thinking", "")
            with ui.expansion(
                f"💭 Thinking ({len(thinking)} символов)",
                icon="psychology",
                value=True,
            ).classes("w-full"):
                with ui.row().classes("w-full justify-end"):
                    _make_copy_btn(lambda: thinking, "Thinking")
                if thinking:
                    ui.textarea(value=thinking).classes(
                        "w-full font-mono text-xs"
                    ).props("readonly outlined autogrow")
                else:
                    ui.label("(пустой)").classes(
                        "text-gray-400 italic"
                    )

            # ── 2. Prompt Pipeline ──
            with ui.expansion(
                "📝 Prompt Pipeline", icon="build"
            ).classes("w-full"):
                with ui.row().classes("w-full justify-end gap-1"):
                    _make_copy_btn(
                        lambda: format_prompt_pipeline_md(trace),
                        "Pipeline MD",
                    )

                # ✨ ЭТАП 3: инфо о размерах промптов
                sys_len = len(trace.get("rendered_system", ""))
                user_len = len(trace.get("rendered_user", ""))
                ui.label(
                    f"System: {sys_len} chars | User: {user_len} chars | "
                    f"Total: {sys_len + user_len} chars"
                ).classes("text-xs text-gray-400 mb-2")

                with ui.row().classes("w-full gap-4"):
                    with ui.column().classes("flex-1 gap-2"):
                        ui.label("📋 Templates").classes(
                            "font-bold text-sm text-gray-500"
                        )
                        with ui.expansion(
                            "System Prompt Template"
                        ).classes("w-full"):
                            with ui.row().classes("w-full justify-end"):
                                _make_copy_btn(
                                    lambda: trace.get(
                                        "system_prompt_template", ""
                                    ),
                                    "System Template",
                                )
                            ui.textarea(
                                value=trace.get(
                                    "system_prompt_template", "(empty)"
                                )
                            ).classes("w-full font-mono text-xs").props(
                                "readonly outlined autogrow"
                            )
                        with ui.expansion(
                            "User Prompt Template"
                        ).classes("w-full"):
                            with ui.row().classes("w-full justify-end"):
                                _make_copy_btn(
                                    lambda: trace.get(
                                        "user_template", ""
                                    ),
                                    "User Template",
                                )
                            ui.textarea(
                                value=trace.get(
                                    "user_template", "(empty)"
                                )
                            ).classes("w-full font-mono text-xs").props(
                                "readonly outlined autogrow"
                            )

                    with ui.column().classes("flex-1 gap-2"):
                        ui.label("🔧 Rendered").classes(
                            "font-bold text-sm text-gray-500"
                        )
                        with ui.expansion("Rendered System").classes(
                            "w-full"
                        ):
                            with ui.row().classes("w-full justify-end"):
                                _make_copy_btn(
                                    lambda: trace.get(
                                        "rendered_system", ""
                                    ),
                                    "Rendered System",
                                )
                            ui.textarea(
                                value=trace.get(
                                    "rendered_system", "(empty)"
                                )
                            ).classes("w-full font-mono text-xs").props(
                                "readonly outlined autogrow"
                            )
                        with ui.expansion("Rendered User").classes(
                            "w-full"
                        ):
                            with ui.row().classes("w-full justify-end"):
                                _make_copy_btn(
                                    lambda: trace.get(
                                        "rendered_user", ""
                                    ),
                                    "Rendered User",
                                )
                            ui.textarea(
                                value=trace.get(
                                    "rendered_user", "(empty)"
                                )
                            ).classes("w-full font-mono text-xs").props(
                                "readonly outlined autogrow"
                            )

            # ── 3. LLM Interaction ──
            llm_responses = raw.get("llm_responses") or []
            with ui.expansion(
                f"🤖 LLM Interaction ({len(llm_responses)} resp.)",
                icon="smart_toy",
            ).classes("w-full"):
                with ui.row().classes("w-full justify-end"):
                    _make_copy_btn(
                        lambda: format_llm_interaction_md(raw),
                        "LLM MD",
                    )
                for resp in llm_responses:
                    attempt = resp.get("attempt", "?")
                    with ui.card().classes("w-full mb-2"):
                        with ui.row().classes("items-center gap-3"):
                            ui.label(
                                f"Attempt {attempt}"
                            ).classes("font-bold text-sm")
                            ui.badge(
                                f"{resp.get('time_sec', 0):.1f}s",
                                color="grey-7",
                            ).props("outline")
                            ui.badge(
                                f"{resp.get('response_chars', 0)} chars",
                                color="grey-7",
                            ).props("outline")

                        usage = resp.get("usage") or {}
                        if usage:
                            with ui.row().classes(
                                "gap-3 text-xs text-gray-600"
                            ):
                                ui.label(
                                    f"in={usage.get('prompt_tokens', 0)}"
                                )
                                ui.label(
                                    f"out={usage.get('completion_tokens', 0)}"
                                )
                                rt = usage.get("reasoning_tokens", 0)
                                if rt:
                                    ui.label(f"reason={rt}")
                                ui.label(
                                    f"total={usage.get('total_tokens', 0)}"
                                )
                        cost = resp.get("cost") or {}
                        if cost and cost.get("total_cost_usd", 0) > 0:
                            ui.label(
                                f"💰 ${cost['total_cost_usd']:.6f}"
                            ).classes("text-xs text-green-700")

                        raw_text = resp.get("raw_response", "")
                        with ui.row().classes("w-full justify-end"):
                            _make_copy_btn(
                                lambda _r=raw_text: _r,
                                f"Response {attempt}",
                            )
                        ui.textarea(value=raw_text).classes(
                            "w-full font-mono text-xs"
                        ).props("readonly outlined autogrow")

            # ── 4. Parser ── ✨ ЭТАП 3: полностью переработан
            parser_attempts = raw.get("parser_attempts") or []
            with ui.expansion(
                f"🔍 Parser ({len(parser_attempts)} attempt(s))",
                icon="manage_search",
            ).classes("w-full"):
                with ui.row().classes("w-full justify-end"):
                    _make_copy_btn(
                        lambda: format_parser_md(raw), "Parser MD"
                    )

                move_selected = raw.get("move_selected") or {}
                if move_selected:
                    ms_from = move_selected.get("from", "?")
                    ms_to = move_selected.get("to", "?")
                    ms_promo = move_selected.get("promotion")
                    ms_str = f"{ms_from}→{ms_to}"
                    if ms_promo:
                        ms_str += f" ={ms_promo}"
                    with ui.row().classes("items-center gap-2 mb-2"):
                        ui.label("Выбранный ход:").classes(
                            "text-sm font-bold"
                        )
                        ui.badge(
                            ms_str, color="green"
                        ).classes("text-sm px-3 py-1")

                for att in parser_attempts:
                    attempt_n = att.get("attempt", "?")
                    is_valid = att.get("valid", False)
                    badge_color = "green" if is_valid else "red"

                    with ui.card().classes("w-full mb-2"):
                        with ui.row().classes("items-center gap-2 mb-1"):
                            ui.label(
                                f"Attempt {attempt_n}"
                            ).classes("font-bold text-sm")
                            ui.badge(
                                "VALID" if is_valid else "INVALID",
                                color=badge_color,
                            )

                        # Coordinates
                        coords = att.get("coordinates_found", [])
                        if coords:
                            with ui.row().classes(
                                "items-center gap-1 mb-1"
                            ):
                                ui.label("Coords:").classes(
                                    "text-xs text-gray-500"
                                )
                                for c in coords:
                                    ui.badge(
                                        c, color="blue-grey-3"
                                    ).props("outline").classes(
                                        "text-xs font-mono"
                                    )

                        # ✨ ЭТАП 3: Пары с яркой цветовой маркировкой
                        pairs = att.get("pairs_tested", [])
                        if pairs:
                            ui.label("Pairs tested:").classes(
                                "text-xs text-gray-500 mt-1"
                            )
                            with ui.row().classes(
                                "gap-1 flex-wrap mt-1"
                            ):
                                for p in pairs:
                                    is_ok = "(OK)" in p
                                    # Более заметные цвета
                                    if is_ok:
                                        ui.badge(p, color="green").classes(
                                            "text-xs font-mono font-bold"
                                        )
                                    else:
                                        ui.badge(
                                            p, color="red-3"
                                        ).props("outline").classes(
                                            "text-xs font-mono"
                                        )

                            # ✨ ЭТАП 3: Summary — сколько OK из скольких
                            ok_count = sum(
                                1 for p in pairs if "(OK)" in p
                            )
                            total_pairs = len(pairs)
                            ui.label(
                                f"→ {ok_count} valid из {total_pairs} "
                                f"проверенных пар "
                                f"(первая валидная: "
                                f"{'пара #' + str(next((i+1 for i, p in enumerate(pairs) if '(OK)' in p), '?'))}"
                                f")"
                            ).classes("text-xs text-gray-500 mt-1")

            # ── 5. Server ──
            server_req = raw.get("server_move_request") or {}
            server_resp = raw.get("server_move_response") or {}
            status_code = server_resp.get("status_code", "?")
            status_color = (
                "green"
                if status_code == 200
                else "orange"
                if status_code == 422
                else "red"
            )

            with ui.expansion(
                f"🌐 Server (HTTP {status_code})",
                icon="dns",
            ).classes("w-full"):
                # ✨ ЭТАП 3: цветной badge статуса
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.badge(
                        f"HTTP {status_code}", color=status_color
                    )
                    resp_data = server_resp.get("data", {})
                    if isinstance(resp_data, dict):
                        if resp_data.get("is_check"):
                            ui.badge("CHECK", color="orange")
                        if resp_data.get("is_checkmate"):
                            ui.badge("CHECKMATE", color="red")
                        if resp_data.get("game_over"):
                            winner = resp_data.get("winner", "?")
                            ui.badge(
                                f"GAME OVER ({winner})",
                                color="purple",
                            )
                        elim = resp_data.get("eliminated_player")
                        if elim:
                            ui.badge(
                                f"ELIMINATED: {elim}", color="red"
                            )

                with ui.row().classes("gap-4 w-full"):
                    with ui.column().classes("flex-1"):
                        ui.label("Request").classes(
                            "font-bold text-sm text-gray-500"
                        )
                        with ui.row().classes("justify-end"):
                            _make_copy_btn(
                                lambda: section_to_json(server_req),
                                "Server Req",
                            )
                        ui.textarea(
                            value=section_to_json(server_req)
                        ).classes("w-full font-mono text-xs").props(
                            "readonly outlined autogrow"
                        )
                    with ui.column().classes("flex-1"):
                        ui.label("Response summary").classes(
                            "font-bold text-sm text-gray-500"
                        )
                        with ui.row().classes("justify-end"):
                            _make_copy_btn(
                                lambda: section_to_json(server_resp),
                                "Server Resp (full)",
                            )
                        summary = {"status_code": status_code}
                        if isinstance(resp_data, dict):
                            for k in (
                                "success",
                                "is_check",
                                "is_checkmate",
                                "is_stalemate",
                                "game_over",
                                "winner",
                                "reason",
                                "eliminated_player",
                                "inherited_pieces",
                            ):
                                v = resp_data.get(k)
                                if v is not None and v != [] and v != False:
                                    summary[k] = v
                        ui.textarea(
                            value=section_to_json(summary)
                        ).classes("w-full font-mono text-xs").props(
                            "readonly outlined autogrow"
                        )

            # ── 6. Statistics ──
            stats = raw.get("statistics") or {}
            if stats:
                with ui.expansion(
                    "📊 Statistics", icon="bar_chart"
                ).classes("w-full"):
                    with ui.row().classes("w-full justify-end"):
                        _make_copy_btn(
                            lambda: section_to_json(stats),
                            "Statistics",
                        )
                    # ✨ ЭТАП 3: визуальные метрики вместо raw JSON
                    with ui.element("div").classes(
                        "grid grid-cols-3 gap-x-6 gap-y-1 text-xs mb-3"
                    ):
                        _stat_row(
                            "Total time",
                            f"{stats.get('time_total_sec', 0):.3f}s",
                        )
                        _stat_row(
                            "LLM time",
                            f"{stats.get('llm_time_sec', 0):.3f}s",
                        )
                        _stat_row(
                            "LLM calls",
                            str(stats.get("llm_calls", 0)),
                        )
                        _stat_row(
                            "Retries",
                            str(stats.get("retries", 0)),
                        )
                        _stat_row(
                            "Prompt chars",
                            f"{stats.get('prompt_chars', 0):,}",
                        )
                        _stat_row(
                            "Response chars",
                            f"{stats.get('response_chars', 0):,}",
                        )
                        _stat_row(
                            "Prompt tokens",
                            f"{stats.get('total_prompt_tokens', 0):,}",
                        )
                        _stat_row(
                            "Completion tokens",
                            f"{stats.get('total_completion_tokens', 0):,}",
                        )
                        _stat_row(
                            "Reasoning tokens",
                            f"{stats.get('total_reasoning_tokens', 0):,}",
                        )
                        _stat_row(
                            "Total tokens",
                            f"{stats.get('total_tokens', 0):,}",
                        )
                        _stat_row(
                            "Cost (calc)",
                            f"${stats.get('total_cost_usd', 0):.6f}",
                        )
                        prc = stats.get("provider_reported_cost_usd")
                        _stat_row(
                            "Cost (provider)",
                            f"${prc:.6f}" if prc else "N/A",
                        )

                    with ui.expansion("Raw statistics JSON").classes(
                        "w-full"
                    ):
                        ui.textarea(
                            value=section_to_json(stats)
                        ).classes("w-full font-mono text-xs").props(
                            "readonly outlined autogrow"
                        )

            # ── 7. Raw JSON ──
            with ui.expansion(
                "📄 Raw JSON (полный trace)", icon="code"
            ).classes("w-full"):
                with ui.row().classes("w-full justify-end"):
                    _make_copy_btn(
                        lambda: section_to_json(raw), "Raw JSON"
                    )
                ui.textarea(
                    value=section_to_json(raw)
                ).classes("w-full font-mono text-xs").props(
                    "readonly outlined"
                ).style("max-height: 600px;")

    def _navigate(delta: int) -> None:
        idx = _state["current_idx"]
        new_idx = idx + delta
        if 0 <= new_idx < len(traces):
            on_navigate(traces[new_idx])

    show_move(None)
    return {"show_move": show_move}


def _stat_row(label: str, value: str) -> None:
    """Рисует строку key: value для статистики."""
    ui.label(label).classes("text-gray-500")
    ui.label(value).classes("font-mono font-bold")
