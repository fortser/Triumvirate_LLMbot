---
name: project-test-generator
description: >
  Generates comprehensive test suite for Triumvirate LLM Bot v2.2.
  Orchestrates two-step process: scenario identification -> test implementation.
  Use when asked to "write tests", "generate test suite", "cover with tests",
  "create tests for", "test coverage", "тесты", "покрытие".
---

# Triumvirate LLM Bot v2.2 — Test Suite Generator

## Project Context

LLM-бот для трёхпользовательской шахматной арены (triumvirate4llm.com).
Архитектура: 12 плоских Python-модулей, asyncio game loop, multi-provider LLM support
(OpenAI-compatible + Anthropic native HTTP). GUI на NiceGUI.
Ключевая особенность: собственная нотация TRIUMVIRATE v4.0 — радиально-кольцевая система
координат для 96-клеточной гексагональной доски.

**Основной пакет:** все .py файлы в корне проекта (плоская структура, без src/)
**Фреймворк:** asyncio + NiceGUI
**HTTP-клиент:** httpx (async)
**Ключевые паттерны:** Оркестратор (BotRunner) + leaf-модули, callback-based GUI

## Two-Step Process

### ШАГ 1: Идентификация сценариев (ПЛАНИРОВАНИЕ)

**Цель:** Составить ПОЛНЫЙ список всех тестовых сценариев ДО написания кода.

Для КАЖДОГО модуля (кроме main.py) выполни анализ:

1. **Публичный интерфейс** — перечисли все публичные функции/методы/классы
2. **Happy path** — основной сценарий использования каждой функции
3. **Edge cases** — граничные значения, пустые коллекции, максимумы
4. **Error paths** — невалидные входы, таймауты, недоступные ресурсы
5. **Инварианты** (используй Skill `property-based-testing`):
   - Roundtrip: `to_server(to_triumvirate(sq)) == sq` для всех 96 клеток
   - Roundtrip: `convert_legal_moves_back(convert_legal_moves(m)) == m`
   - Idempotence: `_sanitize_json_string(sanitize(x)) == sanitize(x)`
   - Invariant: результат MoveParser.parse() всегда None или кортеж из legal_moves
   - Invariant: PricingManager.calc_cost() всегда возвращает non-negative значения
   - Invariant: len(_SERVER_TO_TRI) == len(_TRI_TO_SERVER) == 96
   - No crash: _sanitize_json_string никогда не падает на произвольном тексте
   - No crash: MoveParser.parse() никогда не падает на произвольном тексте
6. **Async tests** — LLMClient, ArenaClient, PricingManager.fetch_openrouter, BotRunner._choose_move

**Формат результата:** Сохрани в `plans/test-scenarios.md` используя шаблон
из [references/scenarios-template.md](references/scenarios-template.md)

**НЕ ПИШИ КОД ТЕСТОВ НА ШАГЕ 1. Только список сценариев.**

### ШАГ 2: Реализация тестов (ИМПЛЕМЕНТАЦИЯ)

**После утверждения списка сценариев** реализуй тесты:

- Skill(`writing-tests`) — философия: поведение > реализация
- Skill(`pytest-patterns`) — механика: fixtures, parametrize, async
- Skill(`property-based-testing`) — инварианты, roundtrip, fuzzing

**Порядок реализации:**

```
1. pyproject.toml             — pytest config, coverage settings
2. tests/conftest.py          — общие fixtures (Settings, game_state, tracer, callbacks)
3. tests/unit/                — чистые функции:
   - test_notation_converter.py  (to_triumvirate, to_server, convert_*)
   - test_move_parser.py         (parse, _from_json, _from_text, _strip_piece_prefix, _norm_promo)
   - test_sanitize_json.py       (_sanitize_json_string — выделен, много edge cases)
   - test_constants.py           (make_bot_name, PROVIDERS structure)
   - test_pricing_calc.py        (calc_cost, extract_usage — чистая логика)
4. tests/integration/         — мульти-модульные с respx:
   - test_settings.py            (Settings load/save, migration, prompt files, .env)
   - test_prompt_builder.py      (build с реальными Settings, game states)
   - test_tracer.py              (init/add/finalize/save cycle, file output)
   - test_llm_client.py          (ask с respx-моками OpenAI + Anthropic)
   - test_arena_client.py        (join/get_state/make_move/resign с respx)
   - test_pricing_fetch.py       (fetch_openrouter с respx)
   - test_bot_runner.py          (_choose_move, _detect_openrouter, stats tracking)
   - test_gui_logic.py            (выделенная бизнес-логика из gui.py closures)
   - test_gui_screens.py          (NiceGUI Screen tests: полные UI-сценарии)
5. tests/property/            — hypothesis:
   - test_notation_roundtrip.py  (roundtrip для всех 96 клеток + convert_legal_moves)
   - test_parser_fuzzing.py      (parse на произвольном тексте: never crash + always legal)
   - test_sanitize_json_fuzzing.py (idempotence + never crash)
```

**Для каждого файла:**
- Запусти `pytest <file> -v` после написания
- Если тесты падают — определи: баг в тесте или баг в коде
- Отслеживай покрытие: `pytest --cov=. --cov-report=term-missing`

## Module Coverage Map

| Модуль                  | Типы тестов                 | Приоритет | Какой навык         | Целевое покрытие |
|-------------------------|-----------------------------|-----------|---------------------|------------------|
| `notation_converter.py` | Unit + Property (roundtrip) | HIGH      | property-based      | 100%             |
| `move_parser.py`        | Unit + Property (fuzzing)   | HIGH      | property-based      | 95%+             |
| `constants.py`          | Unit                        | MEDIUM    | writing-tests       | 100%             |
| `pricing.py`            | Unit + Integration (respx)  | HIGH      | pytest-patterns     | 90%+             |
| `settings.py`           | Integration (tmp_path)      | HIGH      | writing-tests       | 90%+             |
| `prompt_builder.py`     | Integration                 | MEDIUM    | writing-tests       | 90%+             |
| `tracer.py`             | Integration (tmp_path)      | MEDIUM    | writing-tests       | 90%+             |
| `llm_client.py`         | Integration (respx)         | HIGH      | pytest-patterns     | 90%+             |
| `arena_client.py`       | Integration (respx)         | HIGH      | pytest-patterns     | 90%+             |
| `bot_runner.py`         | Integration (partial)       | MEDIUM    | writing-tests       | 70%+             |
| `gui.py`                | Extracted logic + Screen    | MEDIUM    | writing-tests       | 60%+             |
| `main.py`               | **OUT OF SCOPE**            | —         | —                   | —                |

## Coverage Targets

- Минимум **90%** line coverage по всему проекту (без main.py)
- **100%** обязательно для: `notation_converter.py`, `constants.py`
- **95%+** для: `move_parser.py`, `pricing.py`
- **60%+** для: `gui.py` (логика callbacks + основные UI-сценарии)
- Каждый публичный метод — минимум 1 тест
- main.py исключён из coverage (настройка в pyproject.toml)

## Domain-Specific Invariants for Hypothesis

```python
# Roundtrip: notation conversion
# to_server(to_triumvirate(sq)) == sq для всех 96 клеток
# convert_legal_moves_back(convert_legal_moves(moves)) == moves

# Idempotence: JSON sanitization
# _sanitize_json_string(_sanitize_json_string(x)) == _sanitize_json_string(x)

# Invariant: parsed move always legal
# result = parser.parse(text, legal, fmt)
# if result: assert result[0] in legal and result[1] in legal[result[0]]

# Invariant: cost always non-negative
# calc_cost(p, c, r).values() >= 0 for all p, c, r >= 0

# Invariant: lookup tables are bijective
# len(_SERVER_TO_TRI) == len(_TRI_TO_SERVER) == 96
# set(_SERVER_TO_TRI.values()) == set(_TRI_TO_SERVER.keys())

# No crash: sanitizer and parser
# _sanitize_json_string(arbitrary_text) — never raises
# MoveParser.parse(arbitrary_text, legal, fmt) — never raises

# Invariant: make_bot_name never exceeds 80 chars
# len(make_bot_name(provider, model)) <= 80
```

## Стратегия тестирования bot_runner.py

`bot_runner.py` — 837 строк, asyncio-оркестратор. Полный loop не тестируется unit-тестами.

**Что тестировать:**
1. `_detect_openrouter()` — чистая функция на self.s, легко тестируется
2. `_choose_move()` — изолированно с respx-моком LLM + реальными parser/builder/tracer
3. Stats accumulation — проверить что stats корректно суммируются после нескольких вызовов
4. Retry logic в `_choose_move()` — проверить эскалацию temperature, retry hints
5. Fallback to random — проверить что random.choice вызывается когда result=None

**Что НЕ тестировать:**
- `_run()` main loop (too many side effects, asyncio.sleep, state polling)
- GUI callback integration
- Real HTTP to arena/LLM servers

**Как тестировать _choose_move:**
```python
# 1. Create BotRunner with real Settings, real MoveParser, real PromptBuilder
# 2. Mock only LLMClient.ask via respx (HTTP boundary)
# 3. Use real MoveTracer with tmp_path
# 4. Assert: returned (from, to, promo) is valid, stats updated, trace saved
```

## Стратегия тестирования gui.py

`gui.py` — 738 строк. Вся логика внутри `create_gui()` как closures (14 вложенных функций).
Планируется декомпозиция и оптимизация GUI, поэтому тестовое покрытие критично.

### Двухуровневый подход

**Уровень 1: Выделение бизнес-логики (tests/integration/test_gui_logic.py)**

Перед написанием тестов — вынести из closures в отдельные тестируемые функции:

```python
# gui_helpers.py (новый файл, создаётся на этапе тестирования)

def format_state_text(state: dict) -> tuple[str, str]:
    """Форматирует game state для отображения.
    Возвращает (state_markdown, legal_moves_markdown).
    Извлечено из gui.py:_on_state (строки 62-89)."""

def format_game_list(games: list[dict]) -> str:
    """Форматирует список игр для лобби.
    Извлечено из gui.py:on_list_games (строки 300-309)."""

def collect_settings_from_values(
    server_url: str, bot_name: str, auto_bot_name: bool,
    provider: str, base_url: str, api_key: str,
    model: str, temperature: float, max_tokens: int,
    custom_headers_str: str, response_format: str,
    additional_rules: str, max_retries: int,
    auto_skip: bool, fallback_random: bool, use_tri: bool,
) -> dict:
    """Собирает значения UI-полей в dict для Settings.
    Извлечено из gui.py:_collect (строки 101-131)."""

def apply_provider_preset(provider: str) -> dict:
    """Возвращает preset-значения для провайдера.
    Извлечено из gui.py:_on_provider (строки 132-167)."""

def mask_api_key(api_key: str) -> str:
    """Маскирует API-ключ для отображения.
    Извлечено из gui.py:on_test_llm (строки 246-253)."""
```

Тесты для этих функций — обычные unit/integration тесты без NiceGUI.

**Уровень 2: NiceGUI Screen Tests (tests/integration/test_gui_screens.py)**

NiceGUI предоставляет `nicegui.testing` для полных UI-сценариев:

```python
import pytest
from nicegui.testing import Screen

@pytest.fixture
def screen(settings) -> Screen:
    """NiceGUI test screen with our GUI."""
    from gui import create_gui
    create_gui(settings)
    return Screen()

async def test_gui_start_button_launches_bot(screen: Screen):
    """Кнопка 'Запустить' создаёт BotRunner и меняет состояние кнопок."""
    await screen.open("/")
    # Проверяем начальное состояние
    screen.should_contain("Не запущен")
    screen.should_contain("▶ Запустить")

async def test_gui_provider_switch_updates_fields(screen: Screen):
    """Смена провайдера заполняет base_url и model из preset."""
    await screen.open("/")
    # Выбрать провайдер Anthropic -> проверить что поля обновились
    ...

async def test_gui_save_settings_persists(screen: Screen):
    """Кнопка 'Сохранить настройки' вызывает Settings.save()."""
    await screen.open("/")
    ...
```

### Что тестировать в gui.py

| Функция            | Уровень | Что проверяем                                              |
|--------------------|---------|------------------------------------------------------------|
| `_on_state()`      | 1       | Форматирование state -> markdown (check, last_move, legal) |
| `_collect()`       | 1       | Сборка значений полей -> Settings (custom_headers JSON parse) |
| `_on_provider()`   | 1       | Preset-значения для каждого провайдера из PROVIDERS         |
| `_on_fmt()`        | 1       | Правильные hints для каждого формата                        |
| `mask_api_key()`   | 1       | Маскирование ключа (короткий, длинный, пустой)             |
| `on_start()`       | 2       | BotRunner создаётся, кнопки переключаются                   |
| `on_stop()`        | 2       | BotRunner останавливается, кнопки переключаются             |
| `on_test_server()` | 2       | respx мок + UI notification                                 |
| `on_test_llm()`    | 2       | respx мок + log output                                      |
| `on_list_games()`  | 2       | respx мок + games_md content                                |
| `on_resign()`      | 2       | Вызов arena.resign() + log                                  |
| `on_reset_prompts()` | 2     | Файлы промптов перезаписаны                                 |
| Layout rendering   | 2       | Все элементы присутствуют на странице                       |

### Что НЕ тестировать
- CSS-классы и стили (`.classes()`, `.style()`)
- Конкретный визуальный layout (порядок карточек, ширина колонок)
- `ui.run_javascript()` для буфера обмена
- NiceGUI-специфичные `.props()` настройки

## Anti-Patterns to REJECT

- Тесты, которые мокают `move_parser.MoveParser` или `notation_converter` внутри bot_runner
- Тесты, которые мокают `pricing.PricingManager.calc_cost` (это чистая математика)
- Тесты, которые проверяют только "нет исключения" без assert на поведение
- Тесты с хардкоженными данными без объяснения ПОЧЕМУ такие данные
- Тесты, которые ломаются при переименовании приватных полей/методов
- Тесты-дубликаты с минимальными отличиями (-> parametrize)
- `time.sleep()` в тестах вместо condition-based waiting
- Тесты, зависящие от порядка выполнения других тестов
- `unittest.mock.patch` на внутренние модули проекта (только `respx` для HTTP)
- Тесты gui.py, которые проверяют CSS/layout вместо поведения

## See also
- [references/scenarios-template.md](references/scenarios-template.md)
- [references/domain-tests.md](references/domain-tests.md)
- [references/integration-tests.md](references/integration-tests.md)
