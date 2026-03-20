# Triumvirate LLM Bot — GUI v2.2

## Суть и предназначение проекта

Интеллектуальный бот на базе больших языковых моделей (LLM) для игры в шахматы для троих (Three-Player Chess) на платформе [triumvirate4llm.com](https://triumvirate4llm.com).

Бот подключается к игровому серверу через REST API, получает текущее состояние партии, формирует многослойный промпт с описанием позиции на доске и отправляет его в выбранную LLM. Получив ответ, бот парсит ход и передаёт его на сервер — полностью автономный игровой процесс. Управление настройками, аналитика и чат-дипломатия — через встроенный графический веб-интерфейс на базе [NiceGUI](https://nicegui.io/).

---

## Возможности и функционал

### Кросс-модельная поддержка LLM
Пресеты для работы с 6 провайдерами + кастомные эндпоинты:
- **Ollama** — локальные модели (http://localhost:11434/v1)
- **OpenAI API** — GPT-4o, GPT-4o-mini и др.
- **Anthropic** — Claude (нативный протокол с поддержкой `thinking` blocks)
- **OpenRouter** — агрегатор 200+ моделей с автоматическим отслеживанием стоимости
- **LM Studio** — локальные модели (http://localhost:1234/v1)
- **Кастомный URL** — любой OpenAI-совместимый эндпоинт

API-ключи загружаются из `.env` файла: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`.

### Форматы ответа LLM
- **Простой текст** (`simple`) — модель отвечает строкой вида `E2 E4`
- **JSON** (`json`) — объект `{"move_from": "E2", "move_to": "E4"}`
- **JSON с рассуждением** (`json_thinking`) — включает анализ: `{"thinking": "...", "move_from": "E2", "move_to": "E4"}`

### Поддержка двух нотаций
- **Серверная нотация** — буквы A–L, цифры 1–12 (например `A1`, `L12`)
- **TRIUMVIRATE v4.0** — радиально-кольцевая нотация (например `W3/B3.0`, `C/W.B`), улучшающая пространственное восприятие позиции нейросетями. Предвычисленные O(1) lookup-таблицы для 96 клеток.

### Чат-дипломатия между ботами
- Боты отправляют **одно сообщение до 256 символов** вместе с ходом
- Сообщения видны **всем игрокам и зрителям**
- LLM сама решает когда и что писать (опциональное поле `"message"` в JSON-ответе)
- Блеф, союзы, угрозы, дезинформация — полноценная дипломатия в трёхсторонних шахматах
- Инструкции по стратегии чата загружаются из `prompts/chat_instructions.txt`
- История чата (последние 6 сообщений) отображается в GUI и включается в промпт LLM

### Система надёжности
- **Ретраи с эскалацией** — при нелегальном ходе повторный запрос к LLM с повышенной `temperature`. На последней попытке — упрощённый запрос с прямым списком легальных ходов.
- **Фоллбэк на случайный ход** — при исчерпании попыток выбирает случайный легальный ход (`fallback_random`), чтобы избежать поражения по тайм-ауту. Можно отключить.
- **Двойной парсинг** — ответ парсится как JSON, затем как текст через регулярные выражения.
- **Санитизация JSON** — исправление битых переносов строк и markdown-обёрток ` ```json ... ``` `.

### Отслеживание стоимости
Для OpenRouter автоматически загружаются тарифы моделей. На каждый ход рассчитывается стоимость по input/output/reasoning токенам. Накопительная статистика выводится при остановке.

### Трассировка ходов (Observability)
Каждый ход сохраняется как JSON-файл в `logs/game_<id>__<model>/move_NNN.json`:
- Сырое состояние доски от сервера
- Полные промпты (system + user)
- Все запросы и ответы LLM с количеством токенов и стоимостью
- Все попытки парсинга с промежуточными результатами
- API-ошибки (402/429/таймауты) записываются в трейс для диагностики
- Выбранный ход и ответ сервера

### Мульти-бот режим
Параллельный запуск N ботов с разными моделями:
- Автоматический выбор моделей из `models_pool.json` или явный список
- Изолированные настройки для каждого бота (`SettingsOverride`)
- Отдельный лог на каждого бота (`BotLogger`)
- Настраиваемая задержка старта для распределённой нагрузки

### Графический интерфейс (NiceGUI)
- **Десктопный режим** — нативное окно 1440×900
- **Веб-режим** — доступ через браузер
- **Headless режим** — без GUI, только консольный вывод (nicegui не требуется)
- **Левая панель** — настройки (провайдер, модель, промпты, параметры генерации, API-ключи)
- **Правая панель** — три вкладки:
  - **Игра** — состояние доски, легальные ходы, чат-история, события
  - **Лог** — полный лог с копированием и очисткой
  - **Лобби** — список активных игр на сервере
- **Диагностика** — кнопки "Ping сервер" и "Проверить LLM"

---

## Архитектура и модули

Плоская структура — все 14 модулей бота в корне проекта, без подпапок с кодом. GUI полностью отделена от бизнес-логики. Граф зависимостей — DAG без циклов.

| Файл | Ответственность | Зависимости | ~Строк |
|------|-----------------|-------------|--------|
| `main.py` | Точка входа, argparse, запуск GUI/web/headless/multi-bot | gui, settings, multi_bot | 95 |
| `constants.py` | VERSION, PROVIDERS, PROVIDER_ENV_KEY, make_bot_name() | — (leaf) | 95 |
| `settings.py` | Персистентные настройки (JSON r/w), промпты из файлов, .env, миграция | constants | 312 |
| `llm_client.py` | Async HTTP-клиент LLM (OpenAI-compat + Anthropic native) | httpx (leaf) | 122 |
| `arena_client.py` | REST API клиент арены (join, state, move, resign, health) | httpx (leaf) | 82 |
| `pricing.py` | Менеджер тарифов OpenRouter, расчёт стоимости per-move | httpx (leaf) | 169 |
| `prompt_builder.py` | Сборка промптов из шаблонов + game state + chat history | settings | 181 |
| `move_parser.py` | Парсинг ответа LLM → (from, to, promo, message), JSON санитизация | re, json (leaf) | 262 |
| `tracer.py` | Full trace каждого хода → JSON в logs/ | pathlib, json (leaf) | 187 |
| `bot_runner.py` | Основной asyncio game loop, оркестратор | 9 модулей выше | 837 |
| `gui.py` | NiceGUI интерфейс: layout, callbacks, чат-виджет | nicegui, bot_runner, settings | 738 |
| `gui_helpers.py` | Чистые функции из GUI для тестируемости | constants, json | 77 |
| `notation_converter.py` | Конвертер: серверная ↔ TRIUMVIRATE v4.0, O(1) lookup, parse_triumvirate() | — (leaf) | 190 |
| `multi_bot.py` | Оркестратор мульти-ботов: SettingsOverride, BotLogger, параллельный запуск | bot_runner, settings | 250 |

### Граф зависимостей

```
main.py
  ├── gui.py
  │    ├── gui_helpers.py        (leaf)
  │    ├── bot_runner.py
  │    │   ├── llm_client.py     (leaf: httpx)
  │    │   ├── arena_client.py   (leaf: httpx)
  │    │   ├── pricing.py        (leaf: httpx)
  │    │   ├── prompt_builder.py → settings
  │    │   ├── move_parser.py    (leaf: re, json)
  │    │   ├── tracer.py         (leaf: pathlib, json)
  │    │   ├── notation_converter.py (leaf)
  │    │   └── settings.py → constants.py (leaf)
  │    ├── settings.py → constants.py
  │    └── constants.py
  ├── settings.py → constants.py
  └── multi_bot.py → bot_runner, settings
```

---

## Trace Analyzer — аналитика и оценка качества

Отдельный инструмент для анализа trace-логов: веб-приложение + CLI метрики + SmartBot интеграция.

### Trace Viewer (веб-приложение, 4 вкладки)
1. **Overview** — дашборд с метриками, scatter-графики, аномалии
2. **Moves Table** — сортируемая таблица ходов с фильтрами
3. **Thinking Gallery** — карточки reasoning с экспортом в MD/JSON
4. **Move Detail** — детальный разбор одного хода (7 секций)

### CLI метрики
```bash
python -m trace_analyzer.metrics                          # Полный пересчёт → файлы
python -m trace_analyzer.metrics --stdout                 # Таблица рейтинга в консоль
python -m trace_analyzer.metrics --model "gpt-4.1-mini"   # Фильтр по модели
python -m trace_analyzer.metrics --smartbot               # SmartBot объективная оценка
python -m trace_analyzer.metrics --smartbot --model "openai"  # SmartBot + фильтр
```

Результаты сохраняются в `logs/evaluations/`: `metrics.json`, `model_rankings.json`, `game_results.json`.

### SmartBot Integration
Опциональная объективная оценка каждого хода LLM через детерминированный SmartBot:
- **rating_gap** — разница с лучшим ходом SmartBot (0 = идеальный ход)
- **classify_move** — brilliant / good / inaccuracy / mistake / blunder / forced
- **5 компонентов** — material, defense, tactical, positional, risk
- **Threat awareness** — threat_addressed, missed_mate, allows_mate
- **Game context** — player_role (leader/middle/underdog), game_phase, material_advantage

Требует SmartBot (env `SMARTBOT_PATH` или `--smartbot-path`). Без SmartBot — всё работает как раньше.

### Composite Score

| Диапазон | Значение |
|----------|----------|
| 0.70+ | Отличная модель, пригодна для использования |
| 0.50–0.70 | Средняя, работает с ограничениями |
| 0.30–0.50 | Слабая, требует оптимизации промптов |
| < 0.30 | Непригодна |

Формула без SmartBot: Reliability (35%) + Activity (30%) + Tactical (20%) + Efficiency (15%)
Формула с SmartBot: Reliability (20%) + **SmartBot Quality (35%)** + Tactical (15%) + Efficiency (10%) + Win Rate (20%)

---

## Мульти-агентная система оценки

Три компонента для последовательного анализа качества игры LLM-моделей:

```
python -m trace_analyzer.metrics [--smartbot]  →  /evaluate-models  →  /optimize-prompts
       (автометрики + SmartBot)                    (шахматная оценка)    (промпт-рекомендации)
```

| Компонент | Тип | Назначение |
|-----------|-----|-----------|
| **metrics.py** | Python CLI | Автоматические метрики, рейтинг моделей |
| **Model Evaluator** | Claude Code agent | Шахматная оценка ходов, пригодность моделей |
| **Prompt Optimizer** | Claude Code agent | Анализ промптов, рекомендации по оптимизации |
| **Docs Keeper** | Claude Code agent | Актуализация CHANGELOG и оглавления проекта |

Подробная инструкция: `EVALUATION_AGENTS_GUIDE.md`

---

## Входные и выходные форматы

### Входные данные
- **Конфигурация:** `llm_bot_gui_settings_v2.json`, шаблоны `prompts/*.txt`
- **Стэйт сервера (REST JSON):** доска (`board`), легальные ходы (`legal_moves`), текущий игрок, шах, история чата (`chat_history`)
- **Ответы LLM:** текст или JSON с анализом, ходом и опциональным чат-сообщением

### Выходные данные
- **Ход на сервер:**
  ```json
  {
      "from": "A2",
      "to": "A3",
      "promotion": "queen",
      "move_number": 42,
      "message": "Interesting position, let's cooperate against Red!"
  }
  ```
- **Трейс-логи:** `logs/game_<id>__<model>/move_NNN.json` — полная телеметрия хода
- **Метрики:** `logs/evaluations/metrics.json`, `model_rankings.json`, `game_results.json`

---

## Запуск проекта и CLI параметры

### Параметры командной строки

| Аргумент | Описание | Значение / Тип |
|:---------|:---------|:---------------|
| `--web` | Запустить GUI как веб-сервер в браузере | Флаг |
| `--host` | Хост для веб-сервера | Строка, default: `0.0.0.0` |
| `--port` | Порт для веб-сервера | int, default: `8090` |
| `--settings` | Путь к кастомному JSON-файлу настроек | Строка (путь) |
| `--headless` | Запуск без GUI, только консольный вывод | Флаг |
| `--bots N` | Запустить N параллельных ботов | int |
| `--models-pool FILE` | JSON-пул моделей для мульти-бот режима | Строка (путь) |
| `--models M1 M2...` | Явный список моделей для ботов | Строки |
| `--start-delay N` | Задержка (сек) между запусками ботов | int |

### Примеры команд

```bash
# Десктопное окно (1440×900)
python main.py

# Веб-сервер на порту 8090
python main.py --web

# Веб-сервер на другом порту
python main.py --web --port 9000

# Headless режим (без GUI, nicegui не требуется)
python main.py --headless

# Headless с отдельным конфигом
python main.py --headless --settings bot2.json

# Мульти-бот: 3 бота с рандомными моделями из пула
python main.py --headless --bots 3

# Мульти-бот: кастомный пул моделей
python main.py --headless --bots 2 --models-pool custom_pool.json

# Мульти-бот: явный список моделей
python main.py --headless --models openai/gpt-4o-mini anthropic/claude-haiku-4-5-20251001

# Мульти-бот: 5 ботов с задержкой старта 10 сек
python main.py --headless --bots 5 --start-delay 10

# Несколько ботов с разными конфигами (в разных терминалах)
python main.py --web --port 8091 --settings bot_gpt4.json
python main.py --web --port 8092 --settings bot_claude.json

# Trace analyzer — веб-просмотрщик
cd trace_analyzer && python app.py --logs ../logs --port 8091

# Метрики и рейтинг моделей
python -m trace_analyzer.metrics

# Метрики с SmartBot-оценкой
python -m trace_analyzer.metrics --smartbot
python -m trace_analyzer.metrics --smartbot --model "openai"
python -m trace_analyzer.metrics --smartbot --smartbot-path /path/to/smartbot
```

---

## Тестирование

| Метрика | Значение |
|---------|----------|
| Тестов всего | **250** |
| Проходят | **250 (100%)** |
| Покрытие кода | **79.2%** (без gui.py) |
| Время прогона | ~7 сек |

Три уровня тестов:
- **Unit** (103 теста) — constants, notation_converter, move_parser, pricing_calc, sanitize_json
- **Integration** (139 тестов) — settings, prompt_builder, tracer, llm_client, arena_client, pricing_fetch, bot_runner, gui_logic, gui_screens
- **Property-based** (8 тестов) — Hypothesis: notation roundtrip, parser fuzzing, sanitize_json fuzzing

```bash
pytest -v                                  # Все 250 тестов
pytest --cov=. --cov-report=term-missing   # С покрытием
pytest tests/unit/ -v                      # Unit
pytest tests/integration/ -v               # Integration
pytest tests/property/ -v                  # Property-based
```

Подробный отчёт: `TESTING_GUIDE.md`

---

## Структура проекта

```
/ (Корень проекта)
├── main.py, constants.py, settings.py     # Ядро: точка входа, конфиг
├── llm_client.py, arena_client.py         # HTTP-клиенты (LLM + арена)
├── bot_runner.py                          # Основной game loop (оркестратор)
├── prompt_builder.py, move_parser.py      # Промпты и парсинг ответов LLM
├── notation_converter.py                  # Конвертер нотаций (серверная ↔ TRIUMVIRATE)
├── pricing.py, tracer.py                  # Финансы и observability
├── gui.py, gui_helpers.py                 # NiceGUI интерфейс
├── multi_bot.py                           # Мульти-бот оркестратор
├── models_pool.json                       # Пул моделей для мульти-бот режима
│
├── prompts/                               # Шаблоны промптов
│   ├── system_prompt.txt                  # Системный промпт (правила, стратегия)
│   ├── chat_instructions.txt              # Инструкции по чат-дипломатии
│   ├── user_prompt_template.txt           # Шаблон user-промпта (плейсхолдеры)
│   ├── format_json.txt                    # JSON формат ответа
│   ├── format_json_thinking.txt           # JSON с рассуждением
│   └── format_simple.txt                  # Простой текст
│
├── logs/                                  # Трейсы ходов (автогенерируемые)
│   ├── game_<uuid>__<model>/move_NNN.json
│   └── evaluations/                       # Результаты metrics pipeline
│       ├── metrics.json, model_rankings.json, game_results.json
│
├── trace_analyzer/                        # Веб-просмотрщик + CLI метрики
│   ├── app.py, data_loader.py, export_utils.py
│   ├── metrics.py                         # CLI: python -m trace_analyzer.metrics
│   ├── move_metrics.py                    # Per-move метрики (MoveMetrics)
│   ├── aggregator.py                      # Агрегация, composite score
│   ├── smartbot_adapter.py                # SmartBot evaluation adapter
│   ├── smartbot_evaluator.py              # Массовая SmartBot оценка с кэшированием
│   └── views/                             # UI: overview, moves_table, thinking_gallery, move_detail
│
├── tests/                                 # 250 тестов, 79% покрытия
│   ├── unit/ (103), integration/ (139), property/ (8)
│
├── .claude/                               # Конфигурация Claude Code
│   ├── agents/                            # model-evaluator, prompt-optimizer, docs-keeper
│   ├── skills/                            # 5 навыков для тестирования и документации
│   └── hooks/                             # track_changes.py, changelog_reminder.py
│
└── plans/                                 # Архитектурные планы
```

---

## Внешние зависимости

| Пакет | Назначение |
|-------|-----------|
| `nicegui` | GUI framework (не требуется в headless-режиме) |
| `httpx` | Async HTTP client |
| `pytest` | Тестирование |
| `pytest-asyncio` | Async/await тесты |
| `respx` | Мок HTTP-запросов httpx |
| `hypothesis` | Property-based тестирование |
| **SmartBot** | Опционально — объективная оценка ходов (`SMARTBOT_PATH` env) |
