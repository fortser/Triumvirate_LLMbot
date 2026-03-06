# Triumvirate LLM Bot v2.2

LLM-бот для Three-Player Chess Arena (triumvirate4llm.com).
NiceGUI GUI + asyncio game loop + multi-provider LLM support.

## Структура проекта (10 файлов, плоская)

| Файл | Ответственность | ~Строк |
|---|---|---|
| `main.py` | Точка входа, argparse, запуск GUI/web | 30 |
| `constants.py` | PROVIDERS, ENV_KEYS, VERSION, make_bot_name() | 80 |
| `settings.py` | Settings (JSON r/w), дефолтные промпты, DEFAULT_RESPONSE_FORMAT | 140 |
| `llm_client.py` | LLMClient — OpenAI-compat + Anthropic native HTTP | 120 |
| `arena_client.py` | ArenaClient — REST API арены (join, state, move, resign) | 100 |
| `pricing.py` | PricingManager — тарифы OpenRouter, расчёт стоимости | 150 |
| `prompt_builder.py` | PromptBuilder — сборка промптов из шаблонов + game state | 120 |
| `move_parser.py` | MoveParser — парсинг ответа LLM → (from, to, promo) | 90 |
| `tracer.py` | MoveTracer — full trace каждого хода → JSON в logs/ | 180 |
| `bot_runner.py` | BotRunner — основной asyncio game loop, оркестратор | 300 |
| `gui.py` | create_gui() — вся NiceGUI разметка и callbacks | 400 |

## Граф зависимостей (DAG, без циклов)

main → gui → bot_runner → {llm_client, arena_client, pricing, prompt_builder, move_parser, tracer} bot_runner → settings → constants gui → settings → constants gui → constants


## Ключевые правила

- Все файлы 80–400 строк (sweet spot для AI code editors)
- GUI полностью отделена от бизнес-логики
- constants.py — leaf-модуль, ни от чего не зависит
- bot_runner.py — единственный оркестратор, зависит от 6 модулей
- Промпты по умолчанию читаются из prompts/*.txt (fallback — строки в settings.py)

## Команды

- `python main.py` — desktop window (NiceGUI native)
- `python main.py --web` — web server http://localhost:8090
- `python main.py --web --port 9000`
- `python main.py --settings other_config.json` — отдельный конфиг

## Внешние зависимости

- `nicegui` — GUI framework
- `httpx` — async HTTP client
- `websockets` — (опционально, для будущего WS)
