# Python Testing Patterns (Triumvirate LLM Bot)

## Pytest Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
addopts = "-ra -q --strict-markers"
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "slow: long-running tests",
    "integration: integration tests with real dependencies",
]

[tool.coverage.run]
source = ["."]
omit = [
    "tests/*",
    "gui.py",
    "main.py",
    "trace_analyzer/*",
]

[tool.coverage.report]
fail_under = 90
show_missing = true
```

## Fixture Patterns (this project)

```python
import pytest
from pathlib import Path

# --- Settings fixture (isolated, uses tmp_path) ---
@pytest.fixture
def settings(tmp_path):
    """Isolated Settings instance with tmp_path for JSON file."""
    from settings import Settings
    Settings._file = tmp_path / "test_settings.json"
    s = Settings()
    return s

# --- Mock HTTP responses with respx ---
@pytest.fixture
def mock_llm_openai():
    """respx mock for OpenAI-compatible LLM response."""
    import respx, httpx
    with respx.mock:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": '{"move_from":"A2","move_to":"A3"}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
            })
        )
        yield

# --- Factory for game states ---
@pytest.fixture
def make_game_state():
    def _make(current_player="white", move_number=1, legal_moves=None, **kwargs):
        state = {
            "game_status": "playing",
            "current_player": current_player,
            "move_number": move_number,
            "legal_moves": legal_moves or {"A2": ["A3", "A4"]},
            "board": [],
            "last_move": None,
            "check": None,
            "position_3pf": "rnbqkbnr/...",
            "players": [],
        }
        state.update(kwargs)
        return state
    return _make

# --- Tracer fixture (isolated in tmp_path) ---
@pytest.fixture
def tracer(tmp_path):
    from tracer import MoveTracer
    return MoveTracer(tmp_path / "logs")
```

## Mocking External Boundaries Only (respx + httpx)

```python
import respx, httpx

@respx.mock
async def test_llm_client_openai_sends_request():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": "A2 A3"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}
        })
    )
    from llm_client import LLMClient
    client = LLMClient()
    text, body = await client.ask(
        messages=[{"role": "user", "content": "test"}],
        base_url="https://api.openai.com/v1",
        api_key="test-key", model="gpt-4o-mini",
        temperature=0.3, max_tokens=100, compat=True,
    )
    assert text == "A2 A3"
    assert body["usage"]["total_tokens"] == 60
```

## Async Testing

```python
import pytest

# asyncio_mode = "auto" в pyproject.toml означает, что
# все async def test_... автоматически получают event loop

async def test_arena_client_join():
    # respx mock setup...
    client = ArenaClient("https://example.com")
    result = await client.join("TestBot")
    assert result["color"] in ("white", "black", "red")
```

## Parametrize

```python
@pytest.mark.parametrize("input_val,expected", [
    pytest.param("A1", "W3/B3.0", id="corner_A1"),
    pytest.param("D4", "C/W.B", id="center_D4"),
    pytest.param("L12", "R3/W3.3", id="corner_L12"),
])
def test_to_triumvirate(input_val, expected):
    from notation_converter import to_triumvirate
    assert to_triumvirate(input_val) == expected
```

## Tooling Reference

| Tool               | Purpose            | When                         |
|--------------------|--------------------|------------------------------|
| **pytest**          | Test runner        | Always                       |
| **pytest-asyncio**  | Async              | LLMClient, ArenaClient, PricingManager, BotRunner |
| **pytest-cov**      | Coverage           | Always                       |
| **respx**           | HTTP mocking       | LLM/Arena/OpenRouter APIs    |
| **hypothesis**      | Property testing   | notation_converter, move_parser, _sanitize_json |
| **freezegun**       | Time mocking       | MoveTracer timestamps        |
