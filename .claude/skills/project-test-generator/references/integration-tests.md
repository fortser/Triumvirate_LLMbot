# Integration Test Patterns: Triumvirate LLM Bot

## HTTP Client Testing with respx

All three HTTP clients (LLMClient, ArenaClient, PricingManager) use `httpx.AsyncClient`.
Mock them at the HTTP boundary using `respx`, NOT by patching internal methods.

### LLMClient Integration

```python
import respx
import httpx
import pytest
from llm_client import LLMClient

@respx.mock
async def test_llm_openai_compat():
    """OpenAI-compatible endpoint returns text and full body."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": '{"move_from":"A2","move_to":"A3"}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        })
    )
    client = LLMClient()
    text, body = await client.ask(
        messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "test"}],
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=100,
        compat=True,
    )
    assert "move_from" in text
    assert body["usage"]["total_tokens"] == 120

@respx.mock
async def test_llm_anthropic_native():
    """Anthropic native endpoint separates system from user messages."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={
            "content": [{"text": '{"move_from":"A2","move_to":"A3"}'}],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        })
    )
    client = LLMClient()
    text, body = await client.ask(
        messages=[
            {"role": "system", "content": "You are a chess engine"},
            {"role": "user", "content": "Make a move"},
        ],
        base_url="https://api.anthropic.com",
        api_key="sk-ant-test",
        model="claude-haiku-4-5-20251001",
        temperature=0.3,
        max_tokens=100,
        compat=False,
    )
    assert "move_from" in text

@respx.mock
async def test_llm_error_status():
    """HTTP 4xx/5xx raises RuntimeError with details."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "Rate limited"}})
    )
    client = LLMClient()
    with pytest.raises(RuntimeError, match="429"):
        await client.ask(
            messages=[{"role": "user", "content": "test"}],
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=100,
            compat=True,
        )
```

### ArenaClient Integration

```python
@respx.mock
async def test_arena_join():
    """Join stores token, game_id, color from response."""
    respx.post("https://example.com/api/v1/join").mock(
        return_value=httpx.Response(200, json={
            "player_token": "tok-123",
            "game_id": "game-abc",
            "color": "white",
            "status": "waiting",
        })
    )
    from arena_client import ArenaClient
    client = ArenaClient("https://example.com")
    result = await client.join("TestBot", "gpt-4o-mini")
    assert client.token == "tok-123"
    assert client.game_id == "game-abc"
    assert client.color == "white"

@respx.mock
async def test_arena_make_move():
    """make_move returns (status_code, response_data)."""
    respx.post("https://example.com/api/v1/move").mock(
        return_value=httpx.Response(200, json={"is_check": False, "game_over": False})
    )
    from arena_client import ArenaClient
    client = ArenaClient("https://example.com")
    client.token = "tok-123"
    code, data = await client.make_move("A2", "A3", 1)
    assert code == 200
    assert data["is_check"] is False
```

### PricingManager Integration

```python
@respx.mock
async def test_pricing_fetch_openrouter():
    """Fetches and converts pricing from OpenRouter API."""
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(200, json={
            "data": [{
                "id": "openai/gpt-4o-mini",
                "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
            }]
        })
    )
    from pricing import PricingManager
    pm = PricingManager()
    result = await pm.fetch_openrouter("sk-test", "openai/gpt-4o-mini")
    assert result["prompt_per_1m_usd"] == pytest.approx(0.15)
    assert result["completion_per_1m_usd"] == pytest.approx(0.6)
    assert pm._source == "openrouter_api"
```

## Settings Integration (tmp_path)

```python
def test_settings_save_load(tmp_path, monkeypatch):
    """Settings persist to JSON and reload correctly."""
    import settings as settings_mod
    monkeypatch.setattr(settings_mod, '_HERE', tmp_path)
    monkeypatch.setattr(settings_mod, 'SETTINGS_FILE', tmp_path / "s.json")
    from settings import Settings
    Settings._file = tmp_path / "s.json"

    s = Settings()
    s["model"] = "test-model"
    s["temperature"] = 0.7
    s.save()

    Settings._file = tmp_path / "s.json"
    s2 = Settings()
    assert s2["model"] == "test-model"
    assert s2["temperature"] == 0.7
```

## Tracer Integration (tmp_path)

```python
def test_tracer_full_cycle(tmp_path):
    """Complete trace cycle: init -> add data -> finalize -> save -> verify file."""
    from tracer import MoveTracer
    import json

    t = MoveTracer(tmp_path / "logs")
    t.init("game-123", 1, "gpt-4o-mini")
    t.set_model_pricing({"prompt_per_1m": 0.15, "completion_per_1m": 0.6})
    t.add_llm_request(1, [{"role": "user", "content": "test"}])
    t.add_llm_response(1, '{"move_from":"A2","move_to":"A3"}', 35, 1.5,
                        usage={"prompt_tokens": 100, "completion_tokens": 20,
                               "reasoning_tokens": 0, "total_tokens": 120},
                        cost={"total_cost_usd": 0.0001})
    t.set_move_selected("A2", "A3", None)
    t.set_outcome("success")
    t.finalize_statistics()
    t.save()

    trace_file = tmp_path / "logs" / "game_game-123__gpt-4o-mini" / "move_001.json"
    assert trace_file.exists()
    data = json.loads(trace_file.read_text())
    assert data["move_selected"]["from"] == "A2"
    assert data["statistics"]["llm_calls"] == 1
```

## GUI Testing

### Уровень 1: Extracted Logic (gui_helpers.py)

Перед написанием тестов GUI — создать `gui_helpers.py`, извлечь чистые функции
из closures `create_gui()`. Это первый шаг декомпозиции.

```python
# gui_helpers.py — извлечённая логика из gui.py closures

def format_state_text(state: dict) -> tuple[str, str]:
    """Форматирует game state -> (state_markdown, legal_moves_markdown).

    Извлечено из gui.py:_on_state (строки 62-89).
    """
    move_num = state.get("move_number", 0)
    current = state.get("current_player", "?")
    gst = state.get("game_status", "?")
    last = state.get("last_move")
    last_text = f"{last['from_square']}→{last['to_square']}" if last else "—"
    check = state.get("check") or {}
    check_str = ""
    if check.get("is_check"):
        check_str = f"  ⚠️ CHECK: {', '.join(check.get('checked_colors', []))}"

    state_md = (
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
        legal_md = "\n\n".join(lines)
    else:
        legal_md = "*(нет допустимых ходов)*"

    return state_md, legal_md


def format_game_list(games: list[dict]) -> str:
    """Форматирует список игр для лобби -> markdown.

    Извлечено из gui.py:on_list_games (строки 300-309).
    """
    if not games:
        return "*(активных игр нет)*"
    lines = []
    for g in games:
        gid = g.get("game_id", "?")[:8]
        players = ", ".join(
            f"{p.get('color','?')}:{p.get('name','?')}"
            for p in g.get("players", [])
        )
        mn = g.get("move_number", 0)
        lines.append(f"**{gid}…** | {players} | ход {mn}")
    return "\n\n".join(lines)


def collect_settings_from_values(
    server_url: str,
    bot_name: str,
    auto_bot_name: bool,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
    custom_headers_str: str,
    response_format: str,
    additional_rules: str,
    max_retries: int,
    auto_skip: bool,
    fallback_random: bool,
    use_triumvirate: bool,
) -> dict:
    """Собирает значения UI-полей в dict.

    Извлечено из gui.py:_collect (строки 101-131).
    """
    import json as _json
    import os

    from constants import PROVIDER_ENV_KEY

    result = {
        "server_url": server_url.strip(),
        "bot_name": bot_name.strip(),
        "auto_bot_name": auto_bot_name,
        "provider": provider,
        "base_url": base_url.strip(),
        "model": model.strip(),
        "temperature": float(temperature or 0.3),
        "max_tokens": int(max_tokens or 300),
        "response_format": response_format,
        "additional_rules": additional_rules,
        "max_retries": int(max_retries or 3),
        "auto_skip_waiting": auto_skip,
        "fallback_random": fallback_random,
        "use_triumvirate_notation": use_triumvirate,
    }

    # API key: from field or env var fallback
    key = api_key.strip()
    if not key:
        env_var = PROVIDER_ENV_KEY.get(provider, "")
        key = os.environ.get(env_var, "") if env_var else ""
    result["api_key"] = key

    # Custom headers: parse JSON or empty dict
    raw_ch = custom_headers_str.strip()
    if raw_ch:
        try:
            result["custom_headers"] = _json.loads(raw_ch)
        except _json.JSONDecodeError:
            result["custom_headers"] = {}
    else:
        result["custom_headers"] = {}

    return result


def apply_provider_preset(provider: str) -> dict:
    """Возвращает preset-значения для провайдера.

    Извлечено из gui.py:_on_provider (строки 132-167).
    """
    from constants import PROVIDERS
    if provider not in PROVIDERS:
        return {}
    return dict(PROVIDERS[provider])


def mask_api_key(api_key: str) -> str:
    """Маскирует API-ключ для отображения в логе.

    Извлечено из gui.py:on_test_llm (строки 246-253).
    """
    if not api_key:
        return ""
    if len(api_key) > 12:
        return f"{api_key[:8]}...{api_key[-4:]}"
    return "***"


def format_hint(fmt: str) -> str:
    """Возвращает hint-текст для формата ответа.

    Извлечено из gui.py:_on_fmt (строки 169-175).
    """
    hints = {
        "simple": "Ответ: «E2 E4»",
        "json": 'Ответ: {"from":"E2","to":"E4"}',
        "json_thinking": 'Ответ: {"thinking":"…","from":"E2","to":"E4"}',
    }
    return hints.get(fmt, "")
```

### Тесты для gui_helpers.py

```python
# tests/integration/test_gui_logic.py

from gui_helpers import (
    format_state_text,
    format_game_list,
    collect_settings_from_values,
    apply_provider_preset,
    mask_api_key,
    format_hint,
)

def test_format_state_with_check():
    state = {
        "move_number": 5,
        "current_player": "white",
        "game_status": "playing",
        "last_move": {"from_square": "A2", "to_square": "A3"},
        "check": {"is_check": True, "checked_colors": ["black"]},
        "legal_moves": {"E2": ["E3", "E4"]},
    }
    state_md, legal_md = format_state_text(state)
    assert "Ход #5" in state_md
    assert "WHITE" in state_md
    assert "CHECK" in state_md
    assert "black" in state_md
    assert "`E2`" in legal_md

def test_collect_parses_custom_headers():
    result = collect_settings_from_values(
        server_url="https://example.com",
        bot_name="Bot", auto_bot_name=True,
        provider="OpenAI API", base_url="https://api.openai.com/v1",
        api_key="sk-test", model="gpt-4o",
        temperature=0.3, max_tokens=100,
        custom_headers_str='{"X-Custom": "value"}',
        response_format="json", additional_rules="",
        max_retries=3, auto_skip=False,
        fallback_random=True, use_triumvirate=False,
    )
    assert result["custom_headers"] == {"X-Custom": "value"}

def test_mask_api_key_long():
    assert mask_api_key("sk-1234567890abcdef") == "sk-12345...cdef"

def test_mask_api_key_short():
    assert mask_api_key("short") == "***"

def test_preset_openrouter():
    preset = apply_provider_preset("OpenRouter")
    assert "openrouter.ai" in preset["base_url"]
    assert preset["custom_headers"]  # non-empty
```

### Уровень 2: NiceGUI Screen Tests

```python
# tests/integration/test_gui_screens.py
import pytest
from nicegui.testing import Screen

@pytest.fixture
def screen(settings) -> Screen:
    from gui import create_gui
    create_gui(settings)
    screen = Screen()
    return screen

async def test_gui_header_shows_version(screen: Screen):
    await screen.open("/")
    screen.should_contain("Triumvirate LLM Bot")

async def test_gui_all_tabs_present(screen: Screen):
    await screen.open("/")
    screen.should_contain("Игра")
    screen.should_contain("Лог")
    screen.should_contain("Лобби")
```

---

## BotRunner._choose_move Integration

```python
@respx.mock
async def test_choose_move_success(tmp_path, monkeypatch):
    """_choose_move returns valid move from mocked LLM response."""
    import settings as settings_mod
    monkeypatch.setattr(settings_mod, '_HERE', tmp_path)

    # Setup prompts directory with required files
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system_prompt.txt").write_text("You are a chess engine.")
    (prompts_dir / "user_prompt_template.txt").write_text("Move #{{move_number}}")
    (prompts_dir / "format_json_thinking.txt").write_text("Respond with JSON.")

    from settings import Settings
    Settings._file = tmp_path / "settings.json"
    s = Settings()
    s._d["base_url"] = "https://api.openai.com/v1"
    s._d["api_key"] = "sk-test"
    s._d["model"] = "gpt-4o-mini"

    # Mock LLM response
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": '{"move_from":"A2","move_to":"A3"}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        })
    )

    from bot_runner import BotRunner
    logs = []
    runner = BotRunner(s, lambda m: logs.append(m), lambda m: None, lambda s: None)
    runner.tracer = MoveTracer(tmp_path / "logs")

    state = {"game_status": "playing", "current_player": "white",
             "move_number": 1, "legal_moves": {"A2": ["A3", "A4"]},
             "board": [], "last_move": None, "check": None,
             "position_3pf": "test", "players": []}

    result = await runner._choose_move(state, state["legal_moves"])
    assert result == ("A2", "A3", None)
    assert runner.stats["llm_calls"] == 1
```
