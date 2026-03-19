# Multi-Bot Headless Mode

Режим параллельного запуска N ботов одной командой.
Каждый бот получает уникальную LLM-модель из пула и играет свою отдельную игру.

---

## Назначение

Позволяет тестировать и сравнивать разные LLM-модели параллельно:
- Без ручного создания конфигов для каждого бота
- Без запуска нескольких терминалов
- С автоматическим сбором результатов в итоговую таблицу
- С раздельным логированием каждого бота в отдельный файл

---

## Новые файлы

| Файл | Назначение |
|---|---|
| `multi_bot.py` | Оркестратор: параллельный запуск ботов, логирование, итоговая таблица |
| `models_pool.json` | Пул моделей (JSON-массив), из которого выбираются модели для ботов |

---

## Командная строка

### Новые аргументы

| Аргумент | Тип | По умолчанию | Описание |
|---|---|---|---|
| `--bots N` | int | `1` | Количество ботов для параллельного запуска |
| `--models-pool PATH` | str | `models_pool.json` | Путь к JSON-файлу с пулом моделей |
| `--models m1 m2 ...` | str[] | — | Явный список моделей (приоритет над пулом) |
| `--start-delay SEC` | float | из pool файла | Задержка в секундах между запусками ботов (приоритет над pool) |

### Логика активации

Multi-bot режим включается **только** при `--headless` и выполнении одного из условий:
- `--bots` > 1
- указан `--models`

Если ни одно условие не выполнено — запускается обычный одиночный headless-бот.

### Все варианты запуска

```bash
# ─── Обычные режимы (без изменений) ──────────────────────────────────────

python main.py                                  # Desktop window (NiceGUI native)
python main.py --web                            # Web server http://localhost:8090
python main.py --web --port 9000                # Web server на порту 9000
python main.py --web --host 127.0.0.1           # Web server только на localhost
python main.py --headless                       # Одиночный headless-бот
python main.py --headless --settings bot2.json  # Headless с отдельным конфигом
python main.py --settings other.json            # GUI с отдельным конфигом

# ─── Multi-bot режим ─────────────────────────────────────────────────────

# 3 бота, модели выбраны случайно из models_pool.json
python main.py --headless --bots 3

# 5 ботов, модели из пользовательского пула
python main.py --headless --bots 5 --models-pool my_models.json

# 2 бота с явно указанными моделями (пул игнорируется)
python main.py --headless --models openai/gpt-4o-mini anthropic/claude-haiku-4-5-20251001

# 1 бот с явной моделью (эквивалент одиночного, но через multi-bot)
python main.py --headless --bots 1 --models openai/gpt-4o-mini

# Multi-bot + свой конфиг (api_key, server_url, промпты берутся из конфига)
python main.py --headless --bots 3 --settings prod_config.json

# 8 ботов из пула на 5 моделей (модели повторяются)
python main.py --headless --bots 8

# Задержка 10 секунд между запусками (CLI приоритет над pool файлом)
python main.py --headless --bots 3 --start-delay 10

# Без задержки (переопределяет start_delay из models_pool.json)
python main.py --headless --bots 3 --start-delay 0
```

---

## Формат `models_pool.json`

```json
{
  "models": [
    "minimax/minimax-m2.5",
    "moonshotai/kimi-k2.5",
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    "anthropic/claude-haiku-4-5-20251001"
  ],
  "start_delay": 5
}
```

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `models` | string[] | — | Массив полных имён моделей (provider/model) |
| `start_delay` | float | `0` | Задержка в секундах между поочерёдными запусками ботов |

Правила выбора моделей (`_select_models`):
- Если указан `--models` — используется этот список как есть
- Если `--bots N` <= кол-во моделей в пуле — `random.sample` (без повторов)
- Если `--bots N` > кол-во моделей в пуле — `random.choices` (с повторами)

---

## Архитектура `multi_bot.py`

### SettingsOverride

Прокси-обёртка над `Settings`, подменяющая ключи `model` и `auto_skip_waiting`:

```
SettingsOverride(base=Settings, overrides={"model": "...", "auto_skip_waiting": True})
```

- `__getitem__`, `get` — если ключ есть в overrides, возвращает override; иначе делегирует в base
- Виртуальные ключи Settings (`system_prompt`, `user_template`, `api_key`) работают через base
- `save()` — no-op (эфемерные настройки, никогда не пишутся на диск)

### BotResult

Dataclass с итогами работы каждого бота:

| Поле | Тип | Описание |
|---|---|---|
| `index` | int | Порядковый номер бота (0, 1, 2...) |
| `model` | str | Полное имя модели |
| `color` | str | Цвет в игре (WHITE/BLACK/RED) |
| `moves` | int | Количество сделанных ходов |
| `game_result` | str | Итог: finished / no_moves / cancelled / error |
| `cost` | float | Стоимость в USD |
| `duration` | float | Длительность в секундах |
| `error` | str | Текст ошибки (если есть) |

### BotLogger

Раздельное логирование для каждого бота:

- **Файл**: `logs/multi_<YYYYMMDD_HHMMSS>/bot_<N>_<model_short>.log` — полный лог всех событий
- **Консоль**: краткие строки `[HH:MM:SS] [Bot#N model_short] message`, защищённые `asyncio.Lock` от перемешивания

### run_multi_bot (точка входа)

1. Создаёт директорию `logs/multi_<timestamp>/`
2. Для каждой модели создаёт: `SettingsOverride` + `BotLogger` + `BotRunner` → `asyncio.Task`
3. `asyncio.gather()` ждёт завершения всех задач
4. `Ctrl+C` — отменяет все задачи, ждёт корректного завершения до 5 секунд
5. Выводит итоговую таблицу `print_summary()`

---

## Итоговая таблица

После завершения всех ботов выводится сводка:

```
=====================================================================================
 # | Model                          | Color | Moves | Result     |      Cost | Duration
-------------------------------------------------------------------------------------
 0 | gpt-4o-mini                    | WHITE |    42 | finished   |   $0.0032 |  3m 12s
 1 | claude-haiku-4-5-20251001      | RED   |    38 | finished   |   $0.0089 |  2m 58s
 2 | gemini-2.0-flash-001           | BLACK |     0 | error      |   $0.0000 |  0m 03s
=====================================================================================
Total: 3 bots, 80 moves, $0.0121
```

---

## Структура логов

```
logs/
  multi_20260317_143025/          # одна сессия multi-bot
    bot_0_gpt-4o-mini.log         # полный лог бота #0
    bot_1_claude-haiku-4-5-20251001.log
    bot_2_gemini-2.0-flash-001.log
  game_<uuid>__<model>/           # трейсы ходов (создаются BotRunner/Tracer как обычно)
    move_001.json
    ...
```

---

## Что НЕ меняется

- `bot_runner.py` — без изменений, используется как есть
- `settings.py` — без изменений
- `gui.py` — без изменений
- Все существующие режимы (desktop, web, single headless) работают как раньше
- Каждый бот автоматически получает `auto_skip_waiting=True` (не ждёт других игроков)
