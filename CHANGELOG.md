# Changelog

Все значимые изменения в проекте фиксируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased] — 2026-03-22

### Fixed
- **`trace_analyzer/smartbot_adapter.py:315` — `threat_addressed_rate` всегда 0.0 у всех моделей (КРИТИЧЕСКИЙ)**. Опечатка: обращение к несуществующему атрибуту `critical_count` вместо правильного `critical_threats` (из SmartBot `PlayerThreatSummary`). Из-за `hasattr()` guard ошибка не вызывала exception, а тихо возвращала 0 — каскадный эффект через `smartbot_evaluator.py` → `move_metrics.py` → `aggregator.py` обнулял метрику для всех моделей. После исправления: реальные значения 0.85-0.97 (модели адресуют угрозы в 85-97% случаев)

### Changed
- `prompts/user_prompt_template.txt` — удалена строка `Position (3PF): {position_3pf}`, дублировавшая секцию Board в нечитаемом для LLM формате. Экономия ~100-200 токенов на ход
- `settings.py` — удалена строка `Position (3PF)` из fallback-шаблона `_FALLBACK_USER_TEMPLATE` для консистентности с основным шаблоном
- `.claude/agents/prompt-optimizer.md` — исправлены имена переменных шаблона: `{board_state}` → `{board}`, `{game_history}` → `{chat}`, добавлены `{move_number}`, `{current_player}`, `{check}`
- `PROMPT_OPTIMIZATION_PLAN.md` — помечена проблема P-001 как опровергнутая (была основана на сломанной метрике), обновлены целевые значения `threat_addressed_rate`
- `BUGFIX_PLAN.md` — создан план исправления 10 подтверждённых ошибок из анализа от 20 марта; обновлён по результатам выполнения

---

## [Unreleased] — 2026-03-20 16:45

### Added
- `.claude/agents/chess-strategy-analyst.md` — Agent: глубокий анализ шахматной стратегии и тактики LLM-моделей по 7 аспектам (стратегия, тактика, угрозы, атаки, дебют, эндшпиль, адаптация) (`/analyze-strategy`)
- `.claude/skills/chess-strategy-analyst/SKILL.md` — скилл для запуска агента шахматного анализа
- `PROMPT_OPTIMIZATION_PLAN.md` — план оптимизации промптов: 13 выявленных проблем (threat recognition, one-move thinking, piece values, position passivity, opening development, endgame strategy, role adaptation, 3-player dynamics, format errors, chat overhead, thinking structure, token efficiency, coherence)
- **Чат между ботами во время игры** — боты могут отправлять одно текстовое сообщение (до 256 символов) вместе с ходом; сообщения видны всем участникам и зрителям
- `move_parser.py` — метод `extract_message()`: извлекает опциональное поле `"message"` из JSON-ответа LLM, strip whitespace, обрезка до 256 символов
- `prompts/chat_instructions.txt` — инструкции по дипломатии в чате: когда писать/молчать, блеф, союзы, интерпретация чужих сообщений, защита от утечки reasoning в message
- `gui.py` — виджет чата на вкладке "Игра" (markdown-карточка с историей сообщений)
- `CODE_REVIEW_CHAT.md` — отчёт code review по chat feature (3 эксперта, 10 замечаний, план действий)

### Changed
- `arena_client.py` — `make_move()` принимает опциональный параметр `message: str | None`; strip whitespace перед отправкой
- `bot_runner.py` — извлечение chat message из сырого LLM-ответа (`_last_llm_raw`), передача через `arena_client.make_move()`; логирование отправленных сообщений
- `prompt_builder.py` — парсинг `chat_history` из game state, плейсхолдер `{chat}` в user template; подключение `prompts/chat_instructions.txt` как блок `### CHAT DIPLOMACY` в system prompt (между system_prompt.txt и ADDITIONAL RULES)
- `prompts/format_json.txt` — добавлена инструкция по опциональному полю `"message"` с примером
- `prompts/format_json_thinking.txt` — аналогичная инструкция с примером
- `prompts/user_prompt_template.txt` — добавлен плейсхолдер `{chat}` после `{check}`

### Fixed
- `trace_analyzer/smartbot_adapter.py` — изолированный адаптер SmartBot evaluation: `evaluate_position()` оценивает позицию через SmartBot pipeline (parse_3pf → threats → defense → rating → tactical_verify → select_move); lazy import с graceful degradation; `is_smartbot_available()` для проверки наличия SmartBot; dataclass'ы `PositionEvaluation` и `MoveEvaluation` со всеми полями результата; конфигурация через env `SMARTBOT_PATH` или `--smartbot-path`
- `trace_analyzer/smartbot_evaluator.py` — массовый evaluator: `evaluate_traces()` прогоняет SmartBot оценку по всем ходам из трейсов; кэширование по `position_3pf + ход` (LRU dict в памяти); progress reporting каждые 100 ходов; ~7-8 трейсов/сек
- `classify_move()` в `move_metrics.py` — классификация ходов по шкале качества: brilliant (gap ≤ 0) / good (≥ 90%) / inaccuracy (≥ 60%) / mistake (≥ 20%) / blunder (< 20%) / forced (единственный ход) / losing_position (все ходы отрицательные)
- `plans/implementation_plan.md` — детальный план интеграции SmartBot evaluation (13 фаз)
- `plans/smartbot_remaining_todo.md` — TODO оставшихся задач с приоритетами и обоснованиями
- CLI флаги в `metrics.py`: `--smartbot` (включить SmartBot evaluation), `--smartbot-path PATH` (путь к SmartBot), `--check-mates` (проверка мата, заглушка)
- `PROMPT_OPTIMIZATION_ROADMAP.md` — roadmap оптимизации промптов: 6 направлений с причинами, вариантами реализации и ожидаемыми эффектами; основан на анализе 3730 ходов 17 моделей за 18.03.2026
- `.claude/agents/docs-keeper.md` — Agent: актуализация CHANGELOG.md и оглавление_llmbot.md (`/update-docs`); следит за консистентностью документации после изменений в проекте
- `.claude/skills/docs-keeper/SKILL.md` — скилл-триггер: описывает когда и как вызывать агента, форматы записей, правила приоритета документов
- `.claude/hooks/track_changes.py` — PostToolUse хук: при каждом Write/Edit логирует изменённые `.py`/`.md` файлы во временный файл `%TEMP%/claude_changelog_changed.txt`
- `.claude/hooks/changelog_reminder.py` — Stop хук: при завершении сессии читает список изменённых файлов и выводит `systemMessage` с напоминанием обновить CHANGELOG
- `CHANGELOG.md` — файл хронологии изменений проекта (Keep a Changelog формат)

### Fixed
- **`bot_runner.py` — outcome fallback_random перезаписывался на "success"** (КРИТИЧЕСКИЙ). При исчерпании всех retry LLM бот делал случайный ход и устанавливал `outcome="fallback_random"`, но после успешной отправки хода на сервер (HTTP 200) outcome перезаписывался на `"success"`. В результате трейсы и метрики показывали 100% success rate у моделей, которые фактически играли случайными ходами. Теперь fallback сохраняется как `fallback_random_server_ok`
- **`bot_runner.py` — API-ошибки (402/429) терялись из трейсов**. Когда `llm_client.ask()` бросал исключение (ошибка API, таймаут, исчерпание лимитов), `except Exception` ловил ошибку, но не записывал её в `tracer.add_llm_response()`. В результате трейсы содержали `llm_requests: 3` но `llm_responses: 0` без объяснения причины. Теперь ошибка записывается как `"ERROR: <текст>"` в llm_responses
- **`trace_analyzer/` — подсчёт fallback по точному совпадению строки**. aggregator.py, data_loader.py и 4 файла views/ проверяли `outcome == "fallback_random"` точным сравнением. После введения нового формата `fallback_random_server_ok` эти проверки были обновлены на `.startswith("fallback_random")`

### Changed
- `trace_analyzer/move_metrics.py` — MoveMetrics расширен 20+ полями `smartbot_*`: rating, gap, rank, components (material/defense/tactical/positional/risk), threats, exchange, game context; `compute_move_metrics()` принимает optional `smartbot_eval` dict
- `trace_analyzer/aggregator.py` — ModelStats расширен SmartBot-метриками: avg/median/p90 rating_gap, rank_1_rate, top3_rate, blunder/brilliant rates, category distribution, weakness profile, quality_score; GameResult расширен smartbot per-game полями; composite формула обновлена: 20% reliability + 35% SmartBot quality + 15% tactical + 10% efficiency + 20% win_rate (при наличии SmartBot данных); старая формула сохранена как fallback
- `trace_analyzer/metrics.py` — pre-filter трейсов до SmartBot evaluation (раньше фильтр применялся после); расширенная таблица с столбцами SB_Q, Gap, Bri%, Bln% при наличии SmartBot данных
- `CLAUDE.md` — добавлены SmartBot CLI команды, внешняя зависимость SmartBot, smartbot_adapter.py и smartbot_evaluator.py в описание структуры; добавлен раздел "Навигация по проекту" с указанием на CHANGELOG.md и оглавление_llmbot.md; добавлены `.claude/agents/docs-keeper.md`, `.claude/skills/`, `.claude/hooks/` в листинг директорий
- `оглавление_llmbot.md` — добавлен `CHANGELOG.md` в список файлов корня; добавлены `docs-keeper.md`, `docs-keeper/`, секция `hooks/` в дерево `.claude/`; статистика: 3 агента, 5 скиллов, 2 хука
- `.claude/settings.local.json` — добавлены хуки PostToolUse (Write\|Edit → track_changes.py) и Stop (changelog_reminder.py)

---

## [2.2.0] — 2026-03-18 14:09

### Added
- `multi_bot.py` — оркестратор параллельного запуска N ботов с разными моделями
- `models_pool.json` — JSON-пул моделей для мульти-бот режима
- `GO 5 Bots.bat` — скрипт быстрого запуска 5 параллельных ботов
- `.claude/agents/model-evaluator.md` — Claude Code sub-agent для шахматной оценки LLM-моделей (`/evaluate-models`)
- `.claude/agents/prompt-optimizer.md` — Claude Code sub-agent для оптимизации промптов (`/optimize-prompts`)
- `.claude/skills/project-test-generator/` — скилл-оркестратор генерации тестов для проекта
- `.claude/skills/writing-tests/` — скилл: философия тестирования (Testing Trophy)
- `.claude/skills/pytest-patterns/` — скилл: паттерны pytest (fixtures, parametrize, markers)
- `.claude/skills/property-based-testing/` — скилл: Hypothesis property-based тестирование
- `.claude/rules/testing.md` — правила обязательной загрузки скиллов при работе с тестами
- `trace_analyzer/metrics.py` — CLI entry point: `python -m trace_analyzer.metrics`
- `trace_analyzer/move_metrics.py` — per-move метрики (MoveMetrics dataclass + compute)
- `trace_analyzer/aggregator.py` — агрегация per-model/game, composite score с min-max нормализацией
- `logs/evaluations/` — директория результатов metrics pipeline (metrics.json, model_rankings.json, game_results.json)
- `EVALUATION_AGENTS_GUIDE.md` — полное руководство по мульти-агентной системе оценки
- `MULTI_BOT.md` — документация режима мульти-бот запуска
- `plans/multi-agent-evaluation-system.md` — архитектурный план системы оценки
- `plans/trace-evaluation-agent.md` — план агента анализа трейсов
- `CHANGELOG.md` — данный файл (ведение истории изменений)
- `оглавление_llmbot.md` — обновлён: добавлены разделы про агентов, скиллы, CLI метрики

### Changed
- `main.py` — добавлены аргументы CLI: `--headless`, `--bots N`, `--models-pool FILE`, `--models M1 M2...`, `--start-delay N`
- `notation_converter.py` — добавлена функция `parse_triumvirate()` для обратного разбора TRIUMVIRATE нотации; O(1) lookup
- `CLAUDE.md` — обновлена документация структуры с учётом новых модулей и команд

---

## [2.1.0] — 2026-03-15 14:23

### Added
- `gui_helpers.py` — чистые функции, извлечённые из gui.py для тестируемости
- `tests/` — полный тестовый набор: 250 тестов, 79.2% покрытие
  - `tests/unit/` — 5 файлов: constants, notation_converter, move_parser, pricing_calc, sanitize_json (103 теста)
  - `tests/integration/` — 9 файлов: settings, prompt_builder, tracer, llm_client, arena_client, pricing_fetch, bot_runner, gui_logic, gui_screens (139 тестов)
  - `tests/property/` — 3 файла: notation roundtrip, parser fuzzing, sanitize_json fuzzing (8 тестов)
- `tests/conftest.py` — общие фикстуры pytest
- `pyproject.toml` — конфигурация pytest, coverage, asyncio_mode
- `.gitignore` — исключены __pycache__, .env, logs/, llm_bot_gui_settings_v2.json
- `TESTING_GUIDE.md` — полный отчёт о тестовом покрытии
- `plans/test-scenarios.md` — 152 тестовых сценария для 11 модулей

### Removed
- Бинарные файлы `__pycache__/*.pyc` из репозитория
- `llm_bot_gui_settings_v2.json` из репозитория (содержит API-ключи)
- Трейс-логи `logs/` из репозитория (приватные данные)
- `code_review_report.md` из репозитория
- `LLM_report.md` из репозитория
- `claude_start.bat` из репозитория

---

## [2.0.0] — 2026-03-10 21:29

### Added
- `README.md` — расширенное архитектурное описание всех модулей
- `About.md` — краткое описание бота для пользователей
- `оглавление_llmbot.md` — полное оглавление проекта
- `trace_analyzer/` — отдельное веб-приложение для анализа trace-логов
  - `app.py`, `data_loader.py`, `export_utils.py`, `requirements.txt`
  - `views/overview.py`, `moves_table.py`, `thinking_gallery.py`, `move_detail.py`

---

## [1.1.0] — 2026-03-06 19:51

### Fixed
- Исправлены 5 багов в игровом цикле bot_runner.py
- Оптимизация системных запросов к арене

---

## [1.0.1] — 2026-03-06 18:32

### Added
- `notation_converter.py` — конвертер серверная нотация ↔ TRIUMVIRATE v4.0
- Поддержка TRIUMVIRATE v4.0 нотации в `prompt_builder.py` и `move_parser.py`
- Предвычисленные O(1) lookup-таблицы для 96 клеток шахматной доски

---

## [1.0.0] — 2026-03-06 15:14

### Added
- `main.py` — точка входа, argparse (`--web`, `--host`, `--port`, `--settings`)
- `constants.py` — PROVIDERS, PROVIDER_ENV_KEY, VERSION, make_bot_name()
- `settings.py` — персистентные настройки, загрузка .env, промптов из файлов
- `llm_client.py` — async HTTP-клиент (OpenAI-compat + Anthropic native)
- `arena_client.py` — REST клиент шахматной арены (join, get_state, move, resign)
- `pricing.py` — менеджер тарифов OpenRouter, расчёт стоимости per-move
- `prompt_builder.py` — сборщик промптов из шаблонов + game state
- `move_parser.py` — парсинг ответов LLM (JSON / text / regex), промоушен пешек
- `tracer.py` — full trace каждого хода → JSON в logs/
- `bot_runner.py` — основной asyncio game loop, ретраи с эскалацией, fallback
- `gui.py` — NiceGUI интерфейс: левая панель настроек, вкладки Игра/Лог/Лобби
- `prompts/` — system_prompt.txt, user_prompt_template.txt, format_*.txt
- `GO.bat` — скрипт быстрого запуска
- Поддержка провайдеров: Ollama, OpenAI, Anthropic, OpenRouter, LM Studio, Custom URL
- Форматы ответа: simple text, JSON, JSON with thinking
- Система надёжности: ретраи с эскалацией, fallback на случайный ход
- Трассировка ходов: полный JSON-дамп каждого хода в logs/

---

[Unreleased]: https://github.com/user/triumvirate-llm-bot/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/user/triumvirate-llm-bot/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/user/triumvirate-llm-bot/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/user/triumvirate-llm-bot/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/user/triumvirate-llm-bot/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/user/triumvirate-llm-bot/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/user/triumvirate-llm-bot/releases/tag/v1.0.0
