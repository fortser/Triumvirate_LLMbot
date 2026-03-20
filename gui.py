"""NiceGUI графический интерфейс для Triumvirate LLM Bot.

Содержит create_gui() — построение всей GUI, callbacks, layout.
Зависимости: nicegui, bot_runner, settings, constants.
Зависимые: main.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from nicegui import ui

from bot_runner import BotRunner
from constants import VERSION, PROVIDERS, PROVIDER_ENV_KEY, make_bot_name
from llm_client import LLMClient
from settings import (
    DEFAULT_RESPONSE_FORMAT,
    _FALLBACK_SYSTEM,
    _FALLBACK_USER_TEMPLATE,
    _write_prompt_file,
    Settings,
)


def create_gui(settings: Settings) -> None:  # noqa: C901
    """Build the NiceGUI interface."""

    runner: BotRunner | None = None
    _log_lines: list[str] = []
    _recent_entries: list[str] = []

    # ── callbacks ─────────────────────────────────────────────────────────
    def _log(msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        _log_lines.append(line)
        if len(_log_lines) > 2000:
            _log_lines.pop(0)
        log_area.set_value("\n".join(_log_lines))
        _recent_entries.append(line)
        if len(_recent_entries) > 15:
            _recent_entries.pop(0)
        recent_log.set_value("\n".join(_recent_entries[-15:]))

    def _log_err(msg: str) -> None:
        _log(msg)
        ui.notify(msg, type="negative", timeout=8000)

    def _clear_log() -> None:
        _log_lines.clear()
        _recent_entries.clear()
        log_area.set_value("")
        recent_log.set_value("")

    def _status(msg: str) -> None:
        status_lbl.set_text(msg)

    def _on_state(state: dict) -> None:
        move_num = state.get("move_number", 0)
        current = state.get("current_player", "?")
        gst = state.get("game_status", "?")
        last = state.get("last_move")
        last_text = (
            f"{last['from_square']}→{last['to_square']}" if last else "—"
        )
        check = state.get("check") or {}
        check_str = ""
        if check.get("is_check"):
            check_str = (
                f"  ⚠️ CHECK: {', '.join(check.get('checked_colors', []))}"
            )
        state_md.set_content(
            f"**Ход #{move_num}** | Ходит: **{current.upper()}** | "
            f"Статус: *{gst}*{check_str}\n\n"
            f"Последний ход: `{last_text}`"
        )
        legal = state.get("legal_moves", {})
        if legal:
            lines = [
                f"`{src}` → {', '.join(f'`{d}`' for d in sorted(dsts))}"
                for src, dsts in sorted(legal.items())
            ]
            legal_md.set_content("\n\n".join(lines))
        else:
            legal_md.set_content("*(нет допустимых ходов)*")

        # Chat history
        chat = state.get("chat_history", [])
        if chat:
            chat_lines = []
            for msg in chat:
                c = msg.get("color", "?").upper()
                name = msg.get("player_name", c)
                text = msg.get("message", "")
                mn = msg.get("move_number", "?")
                chat_lines.append(f"**#{mn} {name}** ({c}): {text}")
            chat_md.set_content("\n\n".join(chat_lines))
        else:
            chat_md.set_content("*(нет сообщений)*")

    # ── dynamic bot name ──────────────────────────────────────────────────
    def _update_bot_name() -> None:
        if cb_auto_name.value:
            new_name = make_bot_name(sel_provider.value, inp_model.value)
            inp_name.set_value(new_name)

    def _on_model_change(e: Any) -> None:
        _update_bot_name()

    # ── helpers ───────────────────────────────────────────────────────────
    def _collect() -> None:
        settings["server_url"] = inp_server.value.strip()
        settings["bot_name"] = inp_name.value.strip()
        settings["auto_bot_name"] = cb_auto_name.value
        settings["provider"] = sel_provider.value
        settings["base_url"] = inp_base_url.value.strip()
        api_key_ui = inp_api_key.value.strip()
        if not api_key_ui:
            env_var = PROVIDER_ENV_KEY.get(sel_provider.value, "")
            api_key_ui = os.environ.get(env_var, "") if env_var else ""
        settings["api_key"] = api_key_ui
        settings["model"] = inp_model.value.strip()
        settings["temperature"] = float(inp_temp.value or 0.3)
        settings["max_tokens"] = int(inp_tokens.value or 300)
        raw_ch = inp_custom_headers.value.strip()
        if raw_ch:
            try:
                settings["custom_headers"] = json.loads(raw_ch)
            except json.JSONDecodeError:
                settings["custom_headers"] = {}
        else:
            settings["custom_headers"] = {}
        settings["response_format"] = sel_fmt.value
        # NOTE: system_prompt and user_template are NOT collected from GUI.
        # They are read directly from files in prompts/ directory.
        settings["additional_rules"] = ta_rules.value
        settings["max_retries"] = int(inp_retries.value or 3)
        settings["auto_skip_waiting"] = cb_skip.value
        settings["fallback_random"] = cb_fallback.value
        settings["use_triumvirate_notation"] = cb_triumvirate.value

    def _on_provider(e: Any) -> None:
        p = e.value
        if p in PROVIDERS:
            info = PROVIDERS[p]
            inp_base_url.value = info["base_url"]
            inp_model.value = info["model"]
            settings["compat"] = info.get("compat", True)
            settings["custom_headers"] = info.get("custom_headers", {})
            if "temperature" in info:
                inp_temp.value = info["temperature"]
            if "max_tokens" in info:
                inp_tokens.value = info["max_tokens"]
            ch = info.get("custom_headers", {})
            inp_custom_headers.value = (
                json.dumps(ch, ensure_ascii=False) if ch else ""
            )
            if "response_format" in info:
                sel_fmt.set_value(info["response_format"])
                _on_fmt(type("E", (), {"value": info["response_format"]})())
            preset_key = info.get("api_key", "")
            env_var = PROVIDER_ENV_KEY.get(p, "")
            env_val = os.environ.get(env_var, "") if env_var else ""
            if preset_key:
                inp_api_key.value = preset_key
            elif env_val:
                inp_api_key.value = env_val
                _log(
                    f"ℹ️ API-ключ для {p} загружен из переменной среды {env_var}"
                )
            else:
                inp_api_key.value = ""
                if env_var:
                    _log(
                        f"⚠️ API-ключ для {p} не найден (поле пустое, {env_var} не задан)"
                    )
            _update_bot_name()

    def _on_fmt(e: Any) -> None:
        hints = {
            "simple": "Ответ: «E2 E4»",
            "json": 'Ответ: {"from":"E2","to":"E4"}',
            "json_thinking": 'Ответ: {"thinking":"…","from":"E2","to":"E4"}',
        }
        fmt_hint_lbl.set_text(hints.get(e.value, ""))

    # ── button handlers ───────────────────────────────────────────────────
    async def on_start() -> None:
        nonlocal runner
        if runner and runner._running:
            ui.notify("Бот уже запущен", type="warning")
            return
        _collect()
        settings.save()
        runner = BotRunner(settings, _log, _status, _on_state)
        btn_start.disable()
        btn_stop.enable()
        _log("▶️ Запуск бота...")
        runner.start()

    async def on_stop() -> None:
        if runner:
            runner.stop()
            _log("⏹ Бот остановлен")
        btn_start.enable()
        btn_stop.disable()

    async def on_resign() -> None:
        if runner and runner.arena.token:
            try:
                r = await runner.arena.resign()
                _log(
                    f"🏳 Сдался | статус игры: {r.get('game_status','?')}"
                )
            except Exception as e:
                _log_err(f"❌ Ошибка сдачи: {e}")
        else:
            _log("⚠️ Сдача: нет активной игры")
            ui.notify("Нет активной игры", type="warning")

    async def on_skip_waiting() -> None:
        if runner and runner.arena.token:
            try:
                await runner.arena.skip_waiting()
                _log("⏩ Ожидание пропущено")
            except Exception as e:
                _log_err(f"❌ Ошибка skip-waiting: {e}")
        else:
            _log("⚠️ Skip-waiting: нет активной игры")
            ui.notify("Нет активной игры", type="warning")

    async def on_test_server() -> None:
        _collect()
        url = settings["server_url"]
        _log(f"🔍 Ping сервера: {url}")
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(f"{url.rstrip('/')}/api/v1/health")
                r.raise_for_status()
                d = r.json()
            msg = (
                f"✅ Сервер OK | статус={d.get('status','?')} | "
                f"игр={d.get('active_games','?')} | v{d.get('version','?')}"
            )
            _log(msg)
            ui.notify(msg, type="positive")
        except Exception as e:
            _log_err(f"❌ Ping сервера ОШИБКА ({url}): {e}")

    async def on_test_llm() -> None:
        _collect()
        base = settings["base_url"]
        model = settings["model"]
        api_key = settings["api_key"]
        if api_key:
            masked = (
                f"{api_key[:8]}...{api_key[-4:]}"
                if len(api_key) > 12
                else "***"
            )
            _log(
                f"🔍 Тест LLM: {base} | модель={model or '(не указана)'} | "
                f"ключ={masked} ({len(api_key)} символов)"
            )
        else:
            _log(
                f"🔍 Тест LLM: {base} | модель={model or '(не указана)'} | "
                f"⚠️ КЛЮЧ ПУСТОЙ!"
            )
        try:
            client = LLMClient()
            resp_text, resp_body = await client.ask(
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Reply with exactly one word: OK"},
                ],
                base_url=base,
                api_key=settings["api_key"],
                model=model,
                temperature=0.1,
                max_tokens=50,
                compat=settings.get("compat", True),
                custom_headers=settings.get("custom_headers") or {},
            )
            msg = f"✅ LLM ответ: «{resp_text.strip()[:80]}»"
            _log(msg)
            usage = resp_body.get("usage")
            if usage:
                _log(
                    f"   usage: prompt_tokens={usage.get('prompt_tokens','?')} "
                    f"completion_tokens={usage.get('completion_tokens','?')} "
                    f"total={usage.get('total_tokens','?')}"
                )
            ui.notify(msg, type="positive")
        except Exception as e:
            _log_err(f"❌ Тест LLM ОШИБКА ({model} @ {base}): {e}")

    async def on_list_games() -> None:
        _collect()
        url = settings["server_url"]
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{url.rstrip('/')}/api/v1/games")
                r.raise_for_status()
                games = r.json()
            if not games:
                games_md.set_content("*(активных игр нет)*")
                _log("ℹ️ Лобби: активных игр нет")
                return
            lines = []
            for g in games:
                gid = g.get("game_id", "?")[:8]
                players = ", ".join(
                    f"{p.get('color','?')}:{p.get('name','?')}"
                    for p in g.get("players", [])
                )
                mn = g.get("move_number", 0)
                lines.append(f"**{gid}…** | {players} | ход {mn}")
            games_md.set_content("\n\n".join(lines))
            _log(f"ℹ️ Лобби обновлено: {len(games)} игр(ы)")
        except Exception as e:
            _log_err(f"❌ Ошибка загрузки лобби: {e}")

    def on_save_settings() -> None:
        _collect()
        settings.save()
        ui.notify("Настройки сохранены ✔", type="positive")

    def on_reset_prompts() -> None:
        """Reset prompt files to built-in defaults."""
        _write_prompt_file(
            str(settings.system_prompt_path.relative_to(settings._file.parent)),
            _FALLBACK_SYSTEM,
        )
        _write_prompt_file(
            str(settings.user_template_path.relative_to(settings._file.parent)),
            _FALLBACK_USER_TEMPLATE,
        )
        ta_rules.value = ""
        ui.notify(
            "Промпты сброшены к умолчаниям (файлы перезаписаны)",
            type="info",
        )

    # ── layout ────────────────────────────────────────────────────────────
    with ui.header(elevated=True).classes(
        "bg-slate-800 text-white items-center px-4"
    ):
        ui.label(f"♟ Triumvirate LLM Bot  v{VERSION}").classes(
            "text-lg font-bold"
        )
        ui.space()
        status_lbl = ui.label("Не запущен").classes("text-sm opacity-80")

    with ui.element("div").style(
        "display: flex; flex-direction: row; width: 100%;"
        "height: calc(100vh - 52px); overflow: hidden;"
    ):
        # ── LEFT: Settings ─────────────────────────────────────────────
        with ui.element("div").style(
            "width: 380px; min-width: 380px; max-width: 380px;"
            "height: 100%; overflow-y: auto;"
            "background-color: #f9fafb;"
            "border-right: 1px solid #e5e7eb;"
            "padding: 12px; box-sizing: border-box; flex-shrink: 0;"
        ):
            with ui.column().classes("w-full gap-3"):

                # Connection
                with ui.card().classes("w-full"):
                    ui.label("🌐 Подключение").classes(
                        "font-bold text-sm text-gray-600 mb-1"
                    )
                    with ui.row().classes("gap-1 w-full items-end"):
                        inp_server = ui.input(
                            label="URL сервера",
                            value=settings["server_url"],
                        ).classes("flex-1 text-sm")
                        ui.button(
                            icon="wifi_tethering",
                            on_click=on_test_server,
                        ).props("flat dense round").tooltip("Ping сервер")
                    with ui.row().classes("gap-1 w-full items-end"):
                        inp_name = ui.input(
                            label="Имя бота",
                            value=settings["bot_name"],
                        ).classes("flex-1 text-sm")
                        cb_auto_name = ui.checkbox(
                            "Авто",
                            value=settings.get("auto_bot_name", True),
                            on_change=lambda e: _update_bot_name(),
                        ).tooltip(
                            "Автоматически формировать имя из провайдера и модели"
                        )

                # LLM provider
                with ui.card().classes("w-full"):
                    ui.label("🧠 LLM Провайдер").classes(
                        "font-bold text-sm text-gray-600 mb-1"
                    )
                    sel_provider = ui.select(
                        label="Провайдер",
                        options=list(PROVIDERS.keys()),
                        value=settings.get("provider", "OpenAI API"),
                        on_change=_on_provider,
                    ).classes("w-full text-sm")
                    inp_base_url = ui.input(
                        label="Base URL",
                        value=settings["base_url"],
                    ).classes("w-full text-sm")
                    inp_api_key = ui.input(
                        label="API Key",
                        value=settings["api_key"],
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full text-sm")
                    inp_model = ui.input(
                        label="Модель",
                        value=settings["model"],
                        on_change=_on_model_change,
                    ).classes("w-full text-sm")
                    with ui.row().classes("gap-2 w-full"):
                        inp_temp = ui.number(
                            label="Температура",
                            value=settings.get("temperature", 0.3),
                            min=0.0,
                            max=2.0,
                            step=0.05,
                            format="%.2f",
                        ).classes("flex-1 text-sm")
                        inp_tokens = ui.number(
                            label="Max tokens",
                            value=settings.get("max_tokens", 300),
                            min=50,
                            max=65536,
                            step=50,
                        ).classes("flex-1 text-sm")
                    _ch_default = settings.get("custom_headers") or {}
                    inp_custom_headers = ui.input(
                        label="Доп. заголовки (JSON, опционально)",
                        value=(
                            json.dumps(_ch_default, ensure_ascii=False)
                            if _ch_default
                            else ""
                        ),
                        placeholder='{"HTTP-Referer":"https://...","X-Title":"Bot"}',
                    ).classes("w-full font-mono text-xs")
                    ui.label(
                        "Для OpenRouter: HTTP-Referer и X-Title заполняются "
                        "автоматически при выборе провайдера"
                    ).classes("text-xs text-gray-400")

                    ui.button(
                        "Проверить LLM", on_click=on_test_llm
                    ).props("outline dense").classes("w-full mt-1 text-xs")

                # Prompts — file-based (read-only in GUI)
                with ui.card().classes("w-full"):
                    with ui.row().classes(
                        "justify-between items-center mb-1"
                    ):
                        ui.label("📝 Промпты").classes(
                            "font-bold text-sm text-gray-600"
                        )
                        ui.button(
                            "Сброс",
                            on_click=on_reset_prompts,
                        ).props("flat dense size=xs")

                    ui.label(
                        "Промпты хранятся в текстовых файлах. "
                        "Редактируйте их в любом текстовом редакторе."
                    ).classes("text-xs text-gray-500 mb-2")

                    with ui.expansion(
                        "Системный промпт", icon="psychology"
                    ).classes("w-full"):
                        sys_path = settings.system_prompt_path
                        ui.label(f"📄 {sys_path}").classes(
                            "text-xs font-mono text-blue-600 mb-1"
                        )
                        sys_preview = settings["system_prompt"][:200]
                        if len(settings["system_prompt"]) > 200:
                            sys_preview += "…"
                        ui.label(sys_preview).classes(
                            "text-xs text-gray-400 whitespace-pre-line"
                        )

                    with ui.expansion(
                        "Шаблон пользователя", icon="message"
                    ).classes("w-full"):
                        usr_path = settings.user_template_path
                        ui.label(f"📄 {usr_path}").classes(
                            "text-xs font-mono text-blue-600 mb-1"
                        )
                        usr_preview = settings["user_template"][:200]
                        if len(settings["user_template"]) > 200:
                            usr_preview += "…"
                        ui.label(usr_preview).classes(
                            "text-xs text-gray-400 whitespace-pre-line"
                        )
                        ui.label(
                            "Плейсхолдеры: {{move_number}} {{current_player}} "
                            "{{position_3pf}} {{legal_moves}} {{last_move}} "
                            "{{board}} {{check}}"
                        ).classes("text-xs text-gray-400 mt-1")

                    with ui.expansion(
                        "Доп. правила и инструкции", icon="rule"
                    ).classes("w-full"):
                        ta_rules = (
                            ui.textarea(
                                value=settings["additional_rules"],
                                placeholder="Дополнительные инструкции для модели...",
                            )
                            .classes("w-full font-mono text-xs")
                            .props("rows=4 outlined")
                        )

                # Response format
                with ui.card().classes("w-full"):
                    ui.label("📐 Формат ответа").classes(
                        "font-bold text-sm text-gray-600 mb-1"
                    )
                    sel_fmt = ui.select(
                        label="Формат",
                        options={
                            "simple": "Простой текст  (E2 E4)",
                            "json": 'JSON  {"from","to"}',
                            "json_thinking": 'JSON + рассуждение  {"thinking","from","to"}',
                        },
                        value=settings.get(
                            "response_format", "json_thinking"
                        ),
                        on_change=_on_fmt,
                    ).classes("w-full text-sm")
                    fmt_hint_lbl = ui.label("").classes(
                        "text-xs text-gray-500 mt-1"
                    )

                # Bot options
                with ui.card().classes("w-full"):
                    ui.label("⚙️ Параметры бота").classes(
                        "font-bold text-sm text-gray-600 mb-1"
                    )
                    inp_retries = ui.number(
                        label="Макс. повторных запросов к LLM при ошибке",
                        value=settings.get("max_retries", 3),
                        min=1,
                        max=10,
                        step=1,
                    ).classes("w-full text-sm")
                    cb_skip = ui.checkbox(
                        "Авто-пропуск ожидания (skip-waiting)",
                        value=settings.get("auto_skip_waiting", False),
                    )
                    cb_fallback = ui.checkbox(
                        "Случайный ход при сбое LLM",
                        value=settings.get("fallback_random", True),
                    )
                    cb_triumvirate = ui.checkbox(
                        "Нотация Triumvirate (вместо A1-L12)",
                        value=settings.get(
                            "use_triumvirate_notation", False
                        ),
                    ).tooltip(
                        "Конвертировать координаты в радиально-кольцевую "
                        "нотацию Triumvirate v4.0 для LLM. Сервер по-прежнему "
                        "получает стандартные координаты."
                    )

                # Control buttons
                with ui.row().classes("gap-2 w-full"):
                    btn_start = ui.button(
                        "▶ Запустить", on_click=on_start, color="green"
                    ).classes("flex-1")
                    btn_stop = ui.button(
                        "⏹ Стоп", on_click=on_stop, color="red"
                    ).classes("flex-1")
                    btn_stop.disable()

                with ui.row().classes("gap-2 w-full"):
                    ui.button(
                        "🏳 Сдаться", on_click=on_resign
                    ).props("outline").classes("flex-1 text-xs")
                    ui.button(
                        "⏩ Skip wait", on_click=on_skip_waiting
                    ).props("outline").classes("flex-1 text-xs")

                ui.button(
                    "💾 Сохранить настройки", on_click=on_save_settings
                ).props("outline").classes("w-full text-xs")

        # ── RIGHT: Game info + Log ─────────────────────────────────────
        with ui.element("div").style(
            "flex: 1; height: 100%; overflow-y: auto;"
            "padding: 12px; box-sizing: border-box;"
        ):
            with ui.column().classes("w-full gap-3"):

                with ui.tabs().classes("w-full") as tabs:
                    tab_game = ui.tab("Игра", icon="sports_esports")
                    tab_log = ui.tab("Лог", icon="terminal")
                    tab_games = ui.tab("Лобби", icon="list")

                with ui.tab_panels(tabs, value=tab_game).classes(
                    "w-full flex-1"
                ):
                    # ── Tab: Game ─────────────────────────────────────
                    with ui.tab_panel(tab_game):
                        with ui.row().classes(
                            "gap-3 w-full items-start flex-wrap"
                        ):
                            with ui.card().classes("flex-1 min-w-64"):
                                ui.label("Состояние").classes(
                                    "font-bold text-xs text-gray-500 mb-1"
                                )
                                state_md = ui.markdown(
                                    "*Ожидание...*"
                                ).classes("text-sm")

                            with ui.card().classes("flex-1 min-w-64"):
                                ui.label("Допустимые ходы").classes(
                                    "font-bold text-xs text-gray-500 mb-1"
                                )
                                legal_md = ui.markdown("—").classes(
                                    "text-xs font-mono"
                                )

                        with ui.card().classes("w-full"):
                            ui.label("💬 Чат").classes(
                                "font-bold text-xs text-gray-500 mb-1"
                            )
                            chat_md = ui.markdown(
                                "*(нет сообщений)*"
                            ).classes("text-sm")

                        with ui.card().classes("w-full").style(
                            "flex: 1; display: flex; flex-direction: column; "
                            "min-height: 250px;"
                        ):
                            with ui.row().classes(
                                "justify-between items-center mb-1"
                            ):
                                ui.label("Последние события").classes(
                                    "font-bold text-xs text-gray-500"
                                )
                                ui.button(
                                    icon="open_in_new",
                                    on_click=lambda: tabs.set_value(tab_log),
                                ).props(
                                    "flat dense round size=xs"
                                ).tooltip("Открыть полный лог")
                            recent_log = (
                                ui.textarea()
                                .classes("w-full")
                                .props("readonly outlined dense")
                                .style(
                                    "font-family: 'Consolas', 'Courier New', monospace;"
                                    "font-size: 12px; line-height: 1.5;"
                                    "min-height: 250px;"
                                )
                            )

                    # ── Tab: Log ──────────────────────────────────────
                    with ui.tab_panel(tab_log):
                        with ui.row().classes(
                            "justify-between items-center mb-1"
                        ):
                            ui.label("Лог событий").classes(
                                "font-bold text-xs text-gray-500"
                            )
                            with ui.row().classes("gap-1"):
                                btn_copy_log = ui.button(
                                    icon="content_copy",
                                ).props(
                                    "flat dense round size=xs"
                                ).tooltip("Копировать лог в буфер обмена")
                                ui.button(
                                    icon="delete_sweep",
                                    on_click=lambda: _clear_log(),
                                ).props(
                                    "flat dense round size=xs"
                                ).tooltip("Очистить лог")
                        log_area = (
                            ui.textarea()
                            .classes("w-full")
                            .props("readonly outlined dense")
                            .style(
                                "height: calc(100vh - 200px);"
                                "font-family: 'Consolas', 'Courier New', monospace;"
                                "font-size: 12px; line-height: 1.5;"
                            )
                        )

                        def _copy_log() -> None:
                            text = "\n".join(_log_lines)
                            ui.run_javascript(
                                f"navigator.clipboard.writeText({json.dumps(text)})"
                            )
                            ui.notify(
                                f"Скопировано {len(_log_lines)} строк",
                                type="positive",
                                timeout=2000,
                            )

                        btn_copy_log.on_click(_copy_log)

                    # ── Tab: Lobby ────────────────────────────────────
                    with ui.tab_panel(tab_games):
                        with ui.row().classes(
                            "justify-between items-center mb-2"
                        ):
                            ui.label("Активные игры").classes(
                                "font-bold text-xs text-gray-500"
                            )
                            ui.button(
                                icon="refresh",
                                on_click=on_list_games,
                            ).props(
                                "flat dense round size=xs"
                            ).tooltip("Обновить список")
                        games_md = ui.markdown(
                            "*Нажмите ↻ для загрузки*"
                        ).classes("text-sm")

    # ── Post-layout initialisation ────────────────────────────────────
    hints_init = {
        "simple": "Ответ: «E2 E4»",
        "json": 'Ответ: {"from":"E2","to":"E4"}',
        "json_thinking": 'Ответ: {"thinking":"…","from":"E2","to":"E4"}',
    }
    fmt_hint_lbl.set_text(
        hints_init.get(
            settings.get("response_format", "json_thinking"), ""
        )
    )

    if not inp_api_key.value.strip():
        prov = settings.get("provider", "")
        env_var = PROVIDER_ENV_KEY.get(prov, "")
        if env_var:
            env_val = os.environ.get(env_var, "")
            if env_val:
                inp_api_key.set_value(env_val)
                _log(
                    f"ℹ️ API-ключ для {prov} загружен из переменной среды {env_var}"
                )

    if settings.get("auto_bot_name", True):
        initial_name = make_bot_name(
            settings.get("provider", "OpenAI API"),
            settings.get("model", ""),
        )
        inp_name.set_value(initial_name)
