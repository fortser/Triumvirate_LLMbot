"""Основной игровой цикл LLM-бота (asyncio).

Оркестрирует: подключение к арене, поллинг состояния, запрос к LLM,
парсинг хода, отправку хода, ретраи с эскалацией, фоллбэк на случайный ход.

Зависимости: llm_client, arena_client, pricing, prompt_builder,
             move_parser, tracer, settings, constants.
Зависимые: gui.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import time
from pathlib import Path
from typing import Any

from arena_client import ArenaClient
from constants import make_bot_name
from llm_client import LLMClient
from move_parser import COORD_RE, MoveParser
from pricing import PricingManager
from prompt_builder import PromptBuilder
from settings import DEFAULT_RESPONSE_FORMAT, Settings
from tracer import MoveTracer


class BotRunner:
    """Asyncio game loop for the LLM bot."""

    def __init__(
        self,
        settings: Settings,
        on_log: Any,
        on_status: Any,
        on_state: Any,
    ) -> None:
        self.s = settings
        self._log = on_log
        self._set_status = on_status
        self._set_state = on_state
        self._running = False
        self._task: asyncio.Task | None = None
        self.arena = ArenaClient(settings["server_url"])
        self.llm = LLMClient()
        self.builder = PromptBuilder()
        self.parser = MoveParser()
        self.tracer = MoveTracer(Path(__file__).parent / "logs")
        self.pricing = PricingManager()
        self._is_openrouter = False
        self.stats: dict[str, Any] = {
            "moves": 0,
            "llm_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "errors": 0,
            "total_prompt_chars": 0,
            "total_resp_chars": 0,
            "total_llm_time": 0.0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_reasoning_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
        }

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    def _detect_openrouter(self) -> bool:
        provider = self.s.get("provider", "")
        base_url = self.s.get("base_url", "")
        return provider == "OpenRouter" or "openrouter.ai" in base_url.lower()

    # ─── Main loop ────────────────────────────────────────────────────────
    async def _run(self) -> None:
        s = self.s
        try:
            self._is_openrouter = self._detect_openrouter()

            if self._is_openrouter:
                self._set_status("Загрузка тарифов OpenRouter...")
                pricing_info = await self.pricing.fetch_openrouter(
                    s["api_key"], s["model"]
                )
                if self.pricing._source == "openrouter_api":
                    self._log(
                        f"💰 Тарифы OpenRouter для {s['model']}: "
                        f"input=${pricing_info['prompt_per_1m_usd']:.4f}/1M tok, "
                        f"output=${pricing_info['completion_per_1m_usd']:.4f}/1M tok"
                    )
                elif self.pricing._source == "openrouter_model_not_found":
                    self._log(
                        f"⚠️ Модель {s['model']} не найдена в каталоге OpenRouter — "
                        f"стоимость будет $0.00"
                    )
                else:
                    self._log(
                        f"⚠️ Не удалось загрузить тарифы OpenRouter — "
                        f"стоимость будет $0.00"
                    )
            else:
                self.pricing.set_zero()
                self._log(
                    f"ℹ️ Провайдер: {s.get('provider', '?')} — "
                    f"стоимость не отслеживается (только OpenRouter)"
                )

            self._set_status("Проверка сервера...")
            try:
                h = await self.arena.health()
                self._log(
                    f"✅ Сервер: {h.get('status','ok')} | "
                    f"Активных игр: {h.get('active_games','?')} | "
                    f"v{h.get('version','?')}"
                )
            except Exception as e:
                self._log(f"⚠️ Сервер недоступен: {e}")

            self._set_status("Подключение...")
            bot_name = s["bot_name"] or make_bot_name(
                s.get("provider", ""), s.get("model", "")
            )
            join = await self.arena.join(bot_name, s.get("model", ""))
            self._log(
                f"🎮 Joined as «{bot_name}»: цвет={join['color'].upper()} | "
                f"game={join['game_id'][:8]}... | "
                f"статус={join['status']}"
            )
            self._set_status(f"Ожидание | Цвет: {join['color'].upper()}")

            while self._running:
                try:
                    state = await self.arena.get_state()
                except Exception as e:
                    self._log(f"⚠️ get_state error: {e}")
                    await asyncio.sleep(2)
                    continue

                gst = state.get("game_status", "waiting")
                if gst == "playing":
                    break
                if gst == "finished":
                    self._set_status("Игра завершена до начала")
                    self._running = False
                    return

                if s.get("auto_skip_waiting") and gst == "waiting":
                    try:
                        await self.arena.skip_waiting()
                        self._log("⏩ Ожидание пропущено (auto)")
                    except Exception:
                        pass

                self._set_status(f"Ожидание игроков... ({gst})")
                await asyncio.sleep(s.get("poll_interval", 0.5))

            self._log("🏁 Игра началась!")

            while self._running:
                try:
                    state = await self.arena.get_state()
                except Exception as e:
                    self._log(f"⚠️ get_state error: {e}")
                    await asyncio.sleep(2)
                    continue

                gst = state.get("game_status", "playing")
                if gst == "finished":
                    self._log("🏆 Игра завершена")
                    self._set_status("Игра завершена")
                    self._set_state(state)
                    break

                current = state.get("current_player", "")
                move_num = state.get("move_number", 0)
                self._set_state(state)
                self._set_status(
                    f"Ходит: {current.upper()} | "
                    f"Я: {(self.arena.color or '?').upper()} | "
                    f"Ход #{move_num}"
                )

                if current != self.arena.color:
                    await asyncio.sleep(s.get("poll_interval", 0.5))
                    continue

                self.tracer.init(
                    self.arena.game_id or "unknown", move_num, self.s.get("model", "")
                )
                self.tracer.set_model_pricing(self.pricing.get_pricing())
                self.tracer.add_server_interaction("/state", "GET", state)
                self.tracer.set_server_state_raw(state)

                legal = state.get("legal_moves", {})
                if not legal:
                    await asyncio.sleep(0.5)
                    continue

                _trace_saved = False
                try:
                    self._set_status(f"🤔 Думаю... | Ход #{move_num}")
                    result = await self._choose_move(state, legal)

                    if result is None:
                        if s.get("fallback_random", True):
                            src = random.choice(list(legal.keys()))
                            dst = random.choice(legal[src])
                            result = (src, dst, None)
                            self._log(f"🎲 Случайный ход: {src} → {dst}")
                            self.stats["fallbacks"] += 1
                            self.tracer.set_move_selected(src, dst, None)
                            self.tracer.set_outcome("fallback_random")
                        else:
                            self._log("❌ Ход не выбран, пропуск цикла")
                            self.tracer.set_outcome("llm_failed_no_fallback")
                            self.tracer.finalize_statistics()
                            self.tracer.save()
                            _trace_saved = True
                            await asyncio.sleep(1)
                            continue

                    from_sq, to_sq, promo = result
                    move_req: dict[str, Any] = {
                        "from": from_sq,
                        "to": to_sq,
                        "move_number": move_num,
                    }
                    if promo:
                        move_req["promotion"] = promo
                    self.tracer.set_server_move_request(move_req)
                    code, data = await self.arena.make_move(
                        from_sq, to_sq, move_num, promo
                    )
                    self.tracer.set_server_move_response(code, data)
                    self.tracer.set_outcome(
                        "success" if code == 200 else f"server_error_{code}"
                    )
                    self.tracer.finalize_statistics()
                    self.tracer.save()
                    _trace_saved = True

                except Exception as _move_exc:
                    self.tracer.set_outcome(
                        f"exception:{type(_move_exc).__name__}:{_move_exc!s:.120}"
                    )
                    self.tracer.finalize_statistics()
                    self.tracer.save()
                    _trace_saved = True
                    raise

                if code == 200:
                    tags = ""
                    if isinstance(data, dict):
                        if data.get("is_check"):
                            tags += " ♟CHECK"
                        if data.get("is_checkmate"):
                            tags += " 👑CHECKMATE"
                        elim = data.get("eliminated_player")
                        if elim:
                            tags += f" 💀{elim} eliminated"
                        if data.get("game_over"):
                            w = data.get("winner") or "draw"
                            tags += f" 🏆GAME OVER({w})"
                    promo_tag = f" ={promo}" if promo else ""
                    self._log(
                        f"✅ #{move_num} {from_sq}→{to_sq}{promo_tag}{tags}"
                    )
                    self.stats["moves"] += 1

                elif code == 422:
                    if isinstance(data, dict):
                        det = data.get("detail", {})
                        if isinstance(det, dict):
                            self._log(
                                f"❌ Незаконный ход: {det.get('error','')} "
                                f"| осталось попыток: {det.get('attempts_remaining','?')}"
                            )
                        else:
                            self._log(f"❌ 422: {det}")
                    self.stats["errors"] += 1

                elif code == 403:
                    self._log("⚠️ 403: Не мой ход")
                elif code == 409:
                    self._log(
                        "⚠️ 409: Конфликт move_number (ход уже сделан?)"
                    )
                elif code == 410:
                    self._log("🚫 410: Токен недействителен (игрок заменён)")
                    break
                elif code == 429:
                    self._log("⏳ 429: Rate limit, пауза 2с")
                    await asyncio.sleep(2)
                else:
                    self._log(f"❌ {code}: {str(data)[:120]}")
                    self.stats["errors"] += 1

                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._log(f"💥 Критическая ошибка: {e}")
            self._set_status("Ошибка")
        finally:
            self._running = False
            st = self.stats
            avg_time = (
                f"{st['total_llm_time'] / st['llm_calls']:.1f}s"
                if st["llm_calls"] > 0
                else "—"
            )
            cost_str = (
                f"${st['total_cost_usd']:.6f}" if st["total_cost_usd"] > 0 else "$0"
            )
            self._set_status(
                f"Остановлен | ходов={st['moves']} "
                f"llm={st['llm_calls']} "
                f"retry={st['retries']} "
                f"fallback={st['fallbacks']}"
            )
            self._log(
                f"📊 Итого: ходов={st['moves']} | "
                f"LLM-вызовов={st['llm_calls']} | "
                f"повторов={st['retries']} | "
                f"случайных={st['fallbacks']} | "
                f"ошибок={st['errors']}"
            )
            self._log(
                f"📊 Трафик: отправлено={st['total_prompt_chars']} симв. | "
                f"получено={st['total_resp_chars']} симв. | "
                f"общее время LLM={st['total_llm_time']:.1f}s | "
                f"среднее={avg_time}/вызов"
            )
            self._log(
                f"📊 Токены: prompt={st['total_prompt_tokens']} | "
                f"completion={st['total_completion_tokens']} | "
                f"reasoning={st['total_reasoning_tokens']} | "
                f"всего={st['total_tokens']}"
            )
            self._log(f"💰 Общая стоимость: {cost_str}")

    async def _choose_move(
        self, state: dict, legal: dict
    ) -> tuple[str, str, str | None] | None:
        s = self.s
        max_retries = int(s.get("max_retries", 3))
        fmt = s["response_format"]
        messages = self.builder.build(state, s)
        last_raw = ""

        self.tracer.set_prompt_pipeline(
            {
                "system_prompt": s["system_prompt"],
                "user_template": s["user_template"],
                "additional_rules": s.get("additional_rules") or "",
                "response_format_instruction": DEFAULT_RESPONSE_FORMAT.get(fmt, ""),
                "rendered_system": messages[0]["content"] if messages else "",
                "rendered_user_prompt": (
                    messages[1]["content"] if len(messages) > 1 else ""
                ),
            }
        )

        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        legal_count = sum(len(v) for v in legal.values())
        self._log(
            f"📋 Промпт: {prompt_chars} симв. | "
            f"{len(messages)} сообщ. | "
            f"формат={fmt} | "
            f"допустимых ходов: {legal_count}"
        )

        for attempt in range(max_retries):
            if attempt > 0:
                self.stats["retries"] += 1
                is_last = attempt == max_retries - 1
                if is_last:
                    all_pairs = [
                        f"{src} {dst}"
                        for src, dsts in legal.items()
                        for dst in dsts
                    ]
                    retry_ctx = (
                        f"IMPORTANT: Your previous move «{last_raw[:60]}» is ILLEGAL.\n"
                        f"Reply with ONLY two coordinates separated by a space.\n"
                        f"You MUST pick one of these EXACT moves:\n"
                        + "\n".join(all_pairs[:30])
                        + ("\n..." if len(all_pairs) > 30 else "")
                        + "\nJust write the move, nothing else. Example: A2 A3"
                    )
                else:
                    legal_sample = list(legal.items())[:6]
                    legal_hint = "; ".join(
                        f"{src}→[{','.join(dsts[:4])}{',...' if len(dsts)>4 else ''}]"
                        for src, dsts in legal_sample
                    )
                    retry_ctx = (
                        f"Your previous response «{last_raw[:80]}» contained an ILLEGAL move "
                        f"that is NOT in the legal moves list.\n"
                        f"You MUST choose ONLY from the legal moves provided.\n"
                        f"Legal FROM squares: {', '.join(sorted(legal.keys()))}\n"
                        f"Sample: {legal_hint}\n"
                        f"Do NOT repeat the same illegal move."
                    )
                messages = messages + [
                    {"role": "assistant", "content": last_raw or "(empty)"},
                    {"role": "user", "content": retry_ctx},
                ]
                prompt_chars = sum(len(m.get("content", "")) for m in messages)
                self._log(
                    f"🔄 Повтор {attempt+1}/{max_retries}"
                    f"{' [упрощённый формат]' if is_last else ''} "
                    f"(промпт: {prompt_chars} симв., {len(messages)} сообщ.)"
                )

            self._log(
                f"⏳ Запрос к LLM (попытка {attempt+1}/{max_retries})..."
            )
            self.tracer.add_llm_request(attempt + 1, messages)
            t0 = time.time()
            try:
                raw, resp_body = await self.llm.ask(
                    messages=messages,
                    base_url=s["base_url"],
                    api_key=s["api_key"],
                    model=s["model"],
                    temperature=float(s.get("temperature", 0.3)),
                    max_tokens=int(s.get("max_tokens", 300)),
                    compat=bool(s.get("compat", True)),
                    custom_headers=s.get("custom_headers") or {},
                )
                elapsed = time.time() - t0
                self.stats["llm_calls"] += 1
                self.stats["total_prompt_chars"] += prompt_chars
                self.stats["total_llm_time"] += elapsed

                resp_chars = len(raw) if raw else 0
                self.stats["total_resp_chars"] += resp_chars

                usage_data = self.pricing.extract_usage(
                    resp_body, self._is_openrouter
                )
                cost_data = self.pricing.calc_cost(
                    prompt_tokens=usage_data["prompt_tokens"],
                    completion_tokens=usage_data["completion_tokens"],
                    reasoning_tokens=usage_data["reasoning_tokens"],
                )
                cost_data["provider_reported_cost_usd"] = usage_data.get(
                    "provider_reported_cost_usd"
                )

                self.stats["total_prompt_tokens"] += usage_data["prompt_tokens"]
                self.stats["total_completion_tokens"] += usage_data[
                    "completion_tokens"
                ]
                self.stats["total_reasoning_tokens"] += usage_data[
                    "reasoning_tokens"
                ]
                self.stats["total_tokens"] += usage_data["total_tokens"]
                self.stats["total_cost_usd"] += cost_data["total_cost_usd"]

                usage_for_trace = {
                    "prompt_tokens": usage_data["prompt_tokens"],
                    "completion_tokens": usage_data["completion_tokens"],
                    "reasoning_tokens": usage_data["reasoning_tokens"],
                    "total_tokens": usage_data["total_tokens"],
                    "provider_reported_cost_usd": usage_data.get(
                        "provider_reported_cost_usd"
                    ),
                }

                self.tracer.add_llm_response(
                    attempt + 1,
                    raw or "",
                    resp_chars,
                    elapsed,
                    usage=usage_for_trace,
                    cost=cost_data,
                )

                if usage_data["total_tokens"] > 0:
                    tok_info = (
                        f"🔢 Токены: in={usage_data['prompt_tokens']} "
                        f"out={usage_data['completion_tokens']}"
                    )
                    if usage_data["reasoning_tokens"] > 0:
                        tok_info += (
                            f" reasoning={usage_data['reasoning_tokens']}"
                        )
                    tok_info += f" total={usage_data['total_tokens']}"
                    if cost_data["total_cost_usd"] > 0:
                        tok_info += f" | 💰${cost_data['total_cost_usd']:.6f}"
                    prc = usage_data.get("provider_reported_cost_usd")
                    if prc is not None:
                        tok_info += f" (провайдер: ${prc:.6f})"
                    self._log(tok_info)

                if not raw or not raw.strip():
                    self._log(
                        f"⚠️ LLM вернул пустой ответ ({elapsed:.1f}s, "
                        f"попытка {attempt+1}/{max_retries})"
                    )
                    last_raw = "(пустой ответ)"
                    continue

                preview = raw.strip().replace("\n", " ")[:120]
                self._log(
                    f"🤖 LLM ({elapsed:.1f}s, {resp_chars} симв., "
                    f"попытка {attempt+1}): {preview}"
                )

                if fmt in ("json", "json_thinking"):
                    json_start = raw.find("{")
                    json_end = raw.rfind("}")
                    if json_start == -1 or json_end <= json_start:
                        self._log(
                            f"⚠️ JSON не найден в ответе "
                            f"(формат={fmt}, текст начинается с: "
                            f"«{raw.strip()[:50]}»)"
                        )
                    else:
                        json_str = raw[json_start : json_end + 1]
                        try:
                            obj = json.loads(json_str)
                            keys = list(obj.keys())
                            has_from = "from" in obj
                            has_to = "to" in obj
                            has_thinking = "thinking" in obj
                            parts = []
                            if has_thinking:
                                think_len = len(str(obj["thinking"]))
                                parts.append(f"thinking={think_len} симв.")
                            if has_from:
                                raw_f = str(obj["from"]).upper().strip()
                                clean_f = self.parser._strip_piece_prefix(
                                    raw_f
                                )
                                parts.append(
                                    f'from="{raw_f}"'
                                    if clean_f == raw_f
                                    else f'from="{raw_f}"→"{clean_f}"'
                                )
                            if has_to:
                                raw_t = str(obj["to"]).upper().strip()
                                clean_t = self.parser._strip_piece_prefix(
                                    raw_t
                                )
                                parts.append(
                                    f'to="{raw_t}"'
                                    if clean_t == raw_t
                                    else f'to="{raw_t}"→"{clean_t}"'
                                )
                            promo_val = obj.get("promotion")
                            if promo_val:
                                parts.append(f'promo="{promo_val}"')
                            if not has_from or not has_to:
                                parts.append(
                                    f"⚠️ НЕПОЛНЫЙ (ключи: {keys})"
                                )
                            self._log(
                                f"📎 JSON разбор: {' | '.join(parts)}"
                            )
                        except json.JSONDecodeError as je:
                            self._log(
                                f"⚠️ JSON невалиден: {je.msg} "
                                f"(позиция {je.pos}): "
                                f"«{json_str[:60]}»"
                            )

            except Exception as e:
                elapsed = time.time() - t0
                self._log(
                    f"⚠️ LLM ошибка ({elapsed:.1f}s, "
                    f"попытка {attempt+1}/{max_retries}): {e}"
                )
                last_raw = str(e)
                await asyncio.sleep(1)
                continue

            result = self.parser.parse(raw, legal, fmt)

            _upper = raw.upper()
            _coords = COORD_RE.findall(_upper)
            _legal_up = {
                k.upper(): [v.upper() for v in vs] for k, vs in legal.items()
            }
            _pairs = [
                f"{_coords[i]}→{_coords[i+1]}"
                f"({'OK' if _coords[i] in _legal_up and _coords[i+1] in _legal_up.get(_coords[i], []) else 'ILLEGAL'})"
                for i in range(len(_coords) - 1)
            ]
            self.tracer.add_parser_attempt(
                attempt + 1, _coords, _pairs, result is not None
            )

            if result:
                f, t, promo = result
                promo_str = f" ={promo}" if promo else ""
                self._log(
                    f"✔️ Ход распознан: {f}→{t}{promo_str} "
                    f"(валиден: {f} в legal и {t} в legal[{f}])"
                )
                self.tracer.set_move_selected(f, t, promo)
                return result

            last_raw = raw.strip()
            upper = raw.upper()
            coords = COORD_RE.findall(upper)
            if coords:
                pairs_tried = []
                for i in range(len(coords) - 1):
                    c1, c2 = coords[i].upper(), coords[i + 1].upper()
                    legal_up = {
                        k.upper(): [v.upper() for v in vs]
                        for k, vs in legal.items()
                    }
                    in_legal = c1 in legal_up and c2 in legal_up.get(c1, [])
                    pairs_tried.append(
                        f"{c1}→{c2}({'OK' if in_legal else 'ILLEGAL'})"
                    )
                self._log(
                    f"⚠️ Ход не распознан (попытка {attempt+1}/{max_retries}) | "
                    f"найдены координаты: {coords} | "
                    f"пары: {', '.join(pairs_tried)}"
                )
            else:
                self._log(
                    f"⚠️ Ход не распознан (попытка {attempt+1}/{max_retries}) | "
                    f"координаты не найдены в тексте: "
                    f"«{last_raw[:80]}»"
                )

        self._log(f"❌ Все {max_retries} попыток исчерпаны")
        return None
