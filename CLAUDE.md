# Triumvirate LLM Bot v2.2

LLM-бот для Three-Player Chess Arena (triumvirate4llm.com).
NiceGUI GUI + asyncio game loop + multi-provider LLM support.

## Структура проекта (14 файлов, плоская)

| Файл | Ответственность | ~Строк |
|---|---|---|
| `main.py` | Точка входа, argparse, запуск GUI/web/multi-bot | 95 |
| `constants.py` | PROVIDERS, PROVIDER_ENV_KEY, VERSION, make_bot_name() | 95 |
| `settings.py` | Settings (JSON r/w), .env-загрузка, промпты из файлов, миграция legacy | 312 |
| `llm_client.py` | LLMClient — OpenAI-compat + Anthropic native HTTP | 122 |
| `arena_client.py` | ArenaClient — join, get_state, make_move, resign, skip_waiting, list_games | 82 |
| `pricing.py` | PricingManager — тарифы OpenRouter, extract_usage, calc_cost | 169 |
| `prompt_builder.py` | PromptBuilder — сборка промптов, серверная и Triumvirate нотации | 181 |
| `move_parser.py` | MoveParser — парсинг ответа LLM → (from, to, promo), JSON санитизация | 262 |
| `tracer.py` | MoveTracer — full trace каждого хода → JSON в logs/ | 187 |
| `bot_runner.py` | BotRunner — основной asyncio game loop, оркестратор | 837 |
| `gui.py` | create_gui() — вся NiceGUI разметка и callbacks | 738 |
| `notation_converter.py` | Конвертер серверная ↔ TRIUMVIRATE v4.0, O(1) lookup + parse_triumvirate() | 190 |
| `multi_bot.py` | Оркестратор мульти-ботов: SettingsOverride, BotLogger, параллельный запуск | 250 |
| `models_pool.json` | Пул моделей для мульти-бот режима | — |

## Граф зависимостей (DAG, без циклов)

```
main → gui, settings, multi_bot
multi_bot → bot_runner, settings
gui → bot_runner, settings, constants, llm_client
bot_runner → llm_client, arena_client, pricing, prompt_builder,
             move_parser, tracer, settings, constants, notation_converter
prompt_builder → settings
settings → constants
notation_converter  ← leaf (нет зависимостей)
llm_client          ← leaf (только httpx)
arena_client        ← leaf (только httpx)
pricing             ← leaf (только httpx)
move_parser         ← leaf (только stdlib: re, json)
tracer              ← leaf (только stdlib: pathlib, json, time, re)
```

## Ключевые правила

- Плоская структура: все модули бота в корне проекта, без подпапок с кодом
- GUI полностью отделена от бизнес-логики
- constants.py — leaf-модуль, ни от чего не зависит
- bot_runner.py — единственный оркестратор, зависит от 9 модулей
- Промпты хранятся в файлах prompts/*.txt; settings.py хранит только пути к ним
- .env файл в корне проекта автоматически загружается при импорте settings.py
- notation_converter.py — автономный leaf, предвычисляет все 96 клеток при импорте

## Команды

- `python main.py` — desktop window (NiceGUI native, 1440×900)
- `python main.py --web` — web server http://localhost:8090
- `python main.py --web --port 9000`
- `python main.py --headless` — без GUI, только консольный вывод (nicegui не требуется)
- `python main.py --headless --settings bot2.json` — headless с отдельным конфигом
- `python main.py --headless --bots 3` — запуск 3 ботов с рандомными моделями из models_pool.json
- `python main.py --headless --bots 2 --models-pool custom_pool.json` — свой пул моделей
- `python main.py --headless --models openai/gpt-4o-mini anthropic/claude-haiku-4-5-20251001` — явный список моделей
- `python main.py --headless --bots 3 --start-delay 10` — задержка 10с между запусками ботов
- `python main.py --settings other_config.json` — отдельный конфиг (для нескольких ботов одновременно)
- `python -m trace_analyzer.metrics --smartbot` — метрики с объективной SmartBot-оценкой ходов
- `python -m trace_analyzer.metrics --smartbot --model "openai"` — SmartBot-оценка для OpenAI моделей
- `python -m trace_analyzer.metrics --smartbot --smartbot-path /path/to/smartbot` — custom SmartBot path

## Внешние зависимости

- `nicegui` — GUI framework
- `httpx` — async HTTP client
- SmartBot (`T:\test_python\Triumvirate_Smartbot`) — опционально, для `--smartbot` оценки. Путь через env `SMARTBOT_PATH` или `--smartbot-path`

## Директории и дополнительные файлы

```
prompts/               — файлы промптов (читаются settings.py, prompt_builder.py)
  system_prompt.txt
  user_prompt_template.txt
  format_simple.txt
  format_json.txt
  format_json_thinking.txt
  chat_instructions.txt

logs/                  — трейсы ходов (создаётся tracer.py)
  game_<uuid>__<model>/
    move_001.json
    ...

trace_analyzer/        — анализ логов: NiceGUI viewer + metrics pipeline
  app.py, data_loader.py, export_utils.py, requirements.txt
  metrics.py           — CLI: python -m trace_analyzer.metrics [--smartbot]
  move_metrics.py      — per-move автоматические метрики + SmartBot поля
  aggregator.py        — агрегация per-model/game, composite score
  smartbot_adapter.py  — изолированный адаптер SmartBot (lazy import, graceful degradation)
  smartbot_evaluator.py — массовая оценка трейсов через SmartBot с кэшированием
  views/overview.py, moves_table.py, thinking_gallery.py, move_detail.py

logs/evaluations/      — результаты metrics pipeline (автогенерируемые)
  metrics.json, model_rankings.json, game_results.json

.claude/agents/        — агенты Claude Code
  model-evaluator.md   — Agent: шахматная оценка моделей (/evaluate-models)
  prompt-optimizer.md  — Agent: оптимизация промптов (/optimize-prompts)
  docs-keeper.md       — Agent: актуализация CHANGELOG и оглавления (/update-docs)

.claude/skills/        — пользовательские скиллы
  docs-keeper/         — скилл для /update-docs
  project-test-generator/ — оркестратор генерации тестов
  writing-tests/       — философия тестирования
  pytest-patterns/     — паттерны pytest
  property-based-testing/ — Hypothesis PBT

.claude/hooks/         — хуки автоматизации
  track_changes.py     — PostToolUse: логирует изменённые .py/.md в temp-файл
  changelog_reminder.py — Stop: показывает напоминание обновить CHANGELOG

tri/                   — справочные текстовые файлы по нотации доски
```

## Навигация по проекту

Два файла дают полную картину проекта без git diff:

| Файл | Назначение |
|------|-----------|
| **`CHANGELOG.md`** | Хронология всех изменений: Added / Changed / Fixed / Removed. Читай когда нужно быстро понять что и когда менялось. |
| **`оглавление_llmbot.md`** | Полная карта проекта: все модули, агенты, скиллы, хуки, команды CLI, граф зависимостей. Читай для ориентации в структуре. |

**Агент актуализации:** `/update-docs` — обновляет оба файла после значимых изменений.

## Мульти-агентная система оценки

```
python -m trace_analyzer.metrics  →  /evaluate-models  →  /optimize-prompts
       (автометрики)                  (шахматная оценка)    (промпт-рекомендации)
```

Подробнее: `EVALUATION_AGENTS_GUIDE.md`
