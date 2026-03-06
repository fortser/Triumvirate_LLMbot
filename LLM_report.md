# СИСТЕМНЫЙ ПРОМПТ: Эксперт-ассистент по Python кодовой базе

## РОЛЬ И ИДЕНТИЧНОСТЬ

Ты — эксперт по архитектуре программного обеспечения и анализу кода на Python. Ты обладаешь глубокими знаниями в следующих областях:
- Современный Python (3.8+) и его особенности
- Type hints и статическая типизация (PEP 484, PEP 585)
- Паттерны проектирования и архитектурные принципы (SOLID, DRY, KISS)
- Асинхронное программирование (asyncio, async/await)
- Популярные фреймворки (Django, FastAPI, Flask, SQLAlchemy, Pydantic)
- Инструменты экосистемы (pip, poetry, pytest, mypy, ruff)

Твоя задача — помогать пользователю понимать, анализировать, модифицировать и улучшать его Python кодовую базу.

---

## ФОРМАТ КОНТЕКСТА

Пользователь предоставит тебе отчёты о проекте в следующем формате:

### overview.md
Общая сводка проекта: количество файлов, пакеты, ключевые классы, точки входа, зависимости.

### files.md
Карта файлов, показывающая:
- Имена файлов и количество строк
- Импорты и кто импортирует файл
- Классы и функции в каждом файле
- Наличие `if __name__ == "__main__"`

### classes.md
Карта классов, показывающая:
- Имена классов и их расположение
- Иерархию наследования
- Декораторы (@dataclass, @property и т.д.)
- Методы с указанием async/staticmethod/classmethod
- Type hints в сигнатурах

### functions.md
Функции уровня модуля с сигнатурами и декораторами.

### packages.md
Структура пакетов Python:
- Иерархия пакетов и подпакетов
- Публичный API (__all__)
- Документация пакетов

### reference.md
Краткий справочник с группировкой по назначению.

### project_config.md
Конфигурация из pyproject.toml/setup.py: зависимости, версия Python, точки входа.

---

## ПРОТОКОЛ РАБОТЫ

### При получении отчётов:
1. Подтверди получение и резюмируй структуру проекта
2. Определи архитектурный стиль (монолит, микросервисы, библиотека)
3. Отметь используемые паттерны и фреймворки
4. Сообщи о готовности помочь

### При запросах пользователя:
1. Пойми цель запроса
2. Оцени, достаточно ли информации из отчётов
3. Запроси конкретные файлы если нужно

---

## ПРОТОКОЛ ЗАПРОСА ФАЙЛОВ

📁 ЗАПРОС ФАЙЛОВ

Для [выполнения задачи] мне необходимо изучить:
Приоритет 	Файл 	Причина
🔴 Критично 	package/module.py 	[Причина]
🟡 Желательно 	package/utils.py 	[Причина]


---

## PYTHON-СПЕЦИФИЧНЫЕ ЗНАНИЯ

При анализе учитывай:

**Структура проекта:**
- src-layout vs flat-layout
- Относительные vs абсолютные импорты
- `__init__.py` и публичный API

**Type hints:**
- Аннотации в сигнатурах
- Generic типы и TypeVar
- Protocol и structural subtyping

**Асинхронность:**
- async/await паттерны
- Корутины и таски
- Асинхронные контекстные менеджеры

**Тестирование:**
- pytest fixtures
- Моки и патчи
- Параметризация тестов

---

## СТИЛЬ КОММУНИКАЦИИ

1. Используй точные имена модулей, классов и функций из отчётов
2. Структурируй ответы с заголовками
3. Учитывай PEP 8 и идиоматичный Python
4. Предлагай современные решения (3.10+ синтаксис где уместно)


============================================================

# PROJECT REPORTS

# Project: .
Source: Python: 20 py | 5,047 lines | 192 KB
Language: PYTHON

## Packages
trace_analyzer.views/ — 4 modules, 0 subpackages

## Key Classes
MoveTracer (tracer.py)
ArenaClient (arena_client.py)
MoveParser (move_parser.py)
PricingManager (pricing.py)
BotRunner (bot_runner.py)
PromptBuilder (prompt_builder.py)
Settings (settings.py)
LLMClient (llm_client.py)

## Entry Points
- main.py
- trace_analyzer/app.py


---

# File Map

## (root)/
**arena_client.py** (82 lines)
  classes: ArenaClient
  imports: __future__, httpx
  imported_by: bot_runner.py

**bot_runner.py** (768 lines)
  classes: BotRunner
  imports: __future__, asyncio, random, time, pathlib
  imported_by: gui.py

**constants.py** (95 lines)
  functions: make_bot_name
  imports: __future__
  imported_by: bot_runner.py, gui.py

**gui.py** (712 lines)
  functions: create_gui
  imports: __future__, time, httpx, nicegui, bot_runner
  imported_by: main.py

**llm_client.py** (122 lines)
  classes: LLMClient
  imports: __future__, httpx
  imported_by: bot_runner.py, gui.py

**main.py** (81 lines) [has main]
  functions: main
  imports: __future__, argparse, pathlib, nicegui, gui

**move_parser.py** (152 lines)
  classes: MoveParser
  imports: __future__
  imported_by: bot_runner.py

**notation_converter.py** (154 lines)
  functions: _compute_notation, _build_tables, to_triumvirate, to_server, convert_legal_moves +3
  imports: __future__
  imported_by: bot_runner.py

**pricing.py** (169 lines)
  classes: PricingManager
  imports: __future__, httpx
  imported_by: bot_runner.py

**prompt_builder.py** (224 lines)
  classes: PromptBuilder
  imports: __future__, settings
  imported_by: bot_runner.py

**settings.py** (127 lines)
  classes: Settings
  functions: _read_prompt
  imports: __future__, pathlib
  imported_by: bot_runner.py, gui.py, main.py, prompt_builder.py

**tracer.py** (187 lines)
  classes: MoveTracer
  imports: __future__, time, pathlib
  imported_by: bot_runner.py

## trace_analyzer/
**app.py** (201 lines) [has main]
  functions: create_app, main
  imports: __future__, argparse, pathlib, nicegui, data_loader

**data_loader.py** (193 lines)
  functions: scan_traces, _normalize, _extract_model, _extract_thinking, get_games_summary
  imports: __future__, pathlib

**export_utils.py** (163 lines)
  functions: move_to_markdown, moves_to_markdown, section_to_json, format_prompt_pipeline_md, format_parser_md +1
  imports: __future__

## trace_analyzer/views/
**__init__.py** (1 lines) [package init]

**move_detail.py** (627 lines)
  functions: create_move_detail, _stat_row
  imports: __future__, nicegui, export_utils

**moves_table.py** (262 lines)
  functions: create_moves_table
  imports: __future__, nicegui

**overview.py** (384 lines)
  functions: create_overview, _summary_card, _shorten, _metric, _aggregate_by_model +2
  imports: __future__, nicegui, data_loader

**thinking_gallery.py** (343 lines)
  functions: create_thinking_gallery
  imports: __future__, nicegui, export_utils


---

# Class Map

## ArenaClient (arena_client.py)
methods:
  def __init__(self, server_url: str) -> None
  property def _headers(self) -> dict
  async def health(self) -> dict
  async def join(self, name: str, model: str = "") -> dict
  async def get_state(self) -> dict
  async def make_move(self, from_sq: str, to_sq: str, move_number: int, promotion: ... = None) -> tuple[(int, Any)]
  async def skip_waiting(self) -> dict
  async def resign(self) -> dict
  async def list_games(self) -> list
"""HTTP client for the Triumvirate Arena REST API."""

## BotRunner (bot_runner.py)
methods:
  def __init__(self, settings: Settings, on_log: Any, on_status: Any, on_state: Any) -> None
  def start(self) -> None
  def stop(self) -> None
  def _detect_openrouter(self) -> bool
  async def _run(self) -> None
  async def _choose_move(self, state: dict, legal: dict, *, tri_legal: ... = None, tri_board: ... = None, tri_last_move: ... = None) -> ...
"""Asyncio game loop for the LLM bot."""

## LLMClient (llm_client.py)
methods:
  async def ask(self, messages: list[dict], base_url: str, api_key: str, model: str, temperature: float, max_tokens: int, compat: bool, custom_headers: ... = None, timeout: int = 120) -> tuple[(str, dict)]
  async def _openai(self, messages: list[dict], base_url: str, api_key: str, model: str, temperature: float, max_tokens: int, custom_headers: dict, timeout: int) -> tuple[(str, dict)]
  async def _anthropic(self, messages: list[dict], base_url: str, api_key: str, model: str, temperature: float, max_tokens: int, timeout: int) -> tuple[(str, dict)]
"""Sends chat requests to LLM providers.  Returns a tuple of (response_text, full_response_body) so tha..."""

## MoveParser (move_parser.py)
methods:
  def parse(self, text: str, legal: dict, fmt: str, triumvirate: bool = False) -> ...
  def _strip_piece_prefix(self, s: str) -> str
  def _strip_piece_prefix_tri(self, s: str) -> str
  def _from_json(self, text: str, legal_up: dict, triumvirate: bool) -> ...
  def _from_text(self, text: str, legal_up: dict, triumvirate: bool) -> ...
  def _validate(self, f: str, t: str, promo: ..., legal_up: dict) -> ...
  def _norm_promo(self, raw: Any) -> ...
"""Parses and validates LLM response → (from, to, promotion) or None."""

## MoveTracer (tracer.py)
methods:
  def __init__(self, logs_dir: Path) -> None
  def init(self, game_id: str, move_number: int, model: str = "") -> None
  def set_model_pricing(self, pricing: dict) -> None
  def add_server_interaction(self, endpoint: str, method: str, response_raw: Any) -> None
  def set_outcome(self, outcome: str) -> None
  def set_server_state_raw(self, state: dict) -> None
  def set_prompt_pipeline(self, pipeline: dict) -> None
  def add_llm_request(self, attempt: int, messages: list) -> None
  def add_llm_response(self, attempt: int, raw: str, chars: int, time_sec: float, usage: ... = None, cost: ... = None) -> None
  def add_parser_attempt(self, attempt: int, coords_found: list, pairs_tested: list, valid: bool) -> None
  def set_move_selected(self, from_sq: str, to_sq: str, promo: ...) -> None
  def set_server_move_request(self, req: dict) -> None
  def set_server_move_response(self, status_code: int, data: Any) -> None
  def finalize_statistics(self) -> None
  def save(self) -> None
"""Collects full pipeline trace for one move.  v2.1: includes per-attempt token usage, cost breakdown, ..."""

## PricingManager (pricing.py)
methods:
  def __init__(self) -> None
  property def is_loaded(self) -> bool
  def get_pricing(self) -> dict[(str, Any)]
  async def fetch_openrouter(self, api_key: str, model: str) -> dict[(str, Any)]
  def set_zero(self) -> None
  def calc_cost(self, prompt_tokens: int, completion_tokens: int, reasoning_tokens: int = 0) -> dict[(str, float)]
  def extract_usage(self, response_body: dict, is_openrouter: bool) -> dict[(str, Any)]
"""Fetches and caches model pricing from OpenRouter /api/v1/models.  Prices are stored as USD per 1 000..."""

## PromptBuilder (prompt_builder.py)
methods:
  def build(self, state: dict, settings: Settings, *, tri_legal: ... = None, tri_board: ... = None, tri_last_move: ... = None) -> list[dict]
  def _adapt_format_for_tri(self, fmt_instruction: str) -> str
  def _fill_template(self, template: str, subs: dict) -> str
  def _fmt_legal(self, legal: dict) -> str
  def _fmt_board(self, board: list[dict], my_color: str) -> str
  def _fmt_board_tri(self, tri_board: list[dict], my_color: str) -> str
"""Assembles multi-layer prompts from settings + game state."""

## Settings (settings.py)
members:
  _file: Path
  DEFAULTS: dict[(str, Any)]
methods:
  def __init__(self) -> None
  def _load(self) -> None
  def save(self) -> None
  def __getitem__(self, key: str) -> Any
  def __setitem__(self, key: str, value: Any) -> None
  def get(self, key: str, default: Any = None) -> Any
"""JSON-backed application settings."""


---

# Functions

## constants.py
def make_bot_name(provider: str, model: str) -> str

## gui.py
def create_gui(settings: Settings) -> None

## main.py
def main() -> None

## notation_converter.py
def _build_tables() -> tuple[(dict[(str, str)], dict[(str, str)])]
def _compute_notation(sector: str, game_col: int, game_row: int) -> str
def convert_board(board: list[dict]) -> list[dict]
def convert_legal_moves(legal: dict[(str, list[str])]) -> dict[(str, list[str])]
def convert_legal_moves_back(tri_legal: dict[(str, list[str])]) -> dict[(str, list[str])]
def convert_move_back(tri_from: str, tri_to: str) -> tuple[(str, str)]
def to_server(tri_notation: str) -> str
def to_triumvirate(server_notation: str) -> str

## settings.py
def _read_prompt(filename: str, fallback: str) -> str

## trace_analyzer/app.py
def create_app(logs_dir: str) -> None
def main() -> None

## trace_analyzer/data_loader.py
def _extract_model(raw: dict) -> str
def _extract_thinking(raw: dict) -> str
def _normalize(raw: dict) -> dict
def get_games_summary(traces: list[dict]) -> list[dict]
def scan_traces(logs_dir: ...) -> list[dict]

## trace_analyzer/export_utils.py
def format_llm_interaction_md(raw_trace: dict) -> str
def format_parser_md(raw_trace: dict) -> str
def format_prompt_pipeline_md(trace: dict) -> str
def move_to_markdown(trace: dict) -> str
def moves_to_markdown(traces: list[dict]) -> str
def section_to_json(data: Any, indent: int = 2) -> str

## trace_analyzer/views/move_detail.py
def _stat_row(label: str, value: str) -> None
def create_move_detail(traces: list[dict], get_current_trace: Callable[(..., ...)], on_navigate: Callable[(..., None)]) -> dict[(str, Any)]

## trace_analyzer/views/moves_table.py
def create_moves_table(traces: list[dict], on_select_move: Callable[(..., None)], game_filter: Callable[(..., str)]) -> dict[(str, Any)]

## trace_analyzer/views/overview.py
def _aggregate_by_model(traces: list[dict]) -> list[dict]
def _build_scatter_data(traces: list[dict], field: str, y_label: str) -> dict
def _metric(label: str, value: str, color: ... = None) -> None
def _shorten(model: str) -> str
def _show_anomalies(traces: list[dict]) -> None
def _summary_card(label: str, value: str, color: str) -> None
def create_overview(traces: list[dict], game_filter: Callable[(..., str)]) -> dict[(str, Any)]

## trace_analyzer/views/thinking_gallery.py
def create_thinking_gallery(traces: list[dict], game_filter: Callable[(..., str)], on_select_move: Callable[(..., None)]) -> dict[(str, Any)]


---

# Package Structure

## trace_analyzer.views/
modules: move_detail, moves_table, overview, thinking_gallery


---

# Quick Reference

## Core/Main
- main.py
- trace_analyzer/app.py

## API/Routes
- trace_analyzer/views/__init__.py
- trace_analyzer/views/move_detail.py
- trace_analyzer/views/moves_table.py
- trace_analyzer/views/overview.py
- trace_analyzer/views/thinking_gallery.py

## Utils/Helpers
- trace_analyzer/export_utils.py

## Config
- constants.py
- settings.py

## Other
- arena_client.py
- bot_runner.py
- gui.py
- llm_client.py
- move_parser.py
- notation_converter.py
- pricing.py
- prompt_builder.py
- trace_analyzer/data_loader.py
- tracer.py
