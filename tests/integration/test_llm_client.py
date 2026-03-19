"""Tests for llm_client.py — LLMClient HTTP requests via respx."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from llm_client import LLMClient

MESSAGES = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Say hi"},
]


@pytest.fixture()
def client():
    return LLMClient()


# ── OpenAI path ──────────────────────────────────────────────────────────────

@respx.mock
async def test_openai_returns_text_and_body(client):
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })
    )
    text, body = await client.ask(
        MESSAGES, "https://api.openai.com/v1", "sk-test",
        "gpt-4o", 0.3, 100, compat=True,
    )
    assert text == "Hello!"
    assert body["usage"]["prompt_tokens"] == 10


@respx.mock
async def test_openai_correct_payload(client):
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })
    )
    await client.ask(
        MESSAGES, "https://api.openai.com/v1", "sk-test",
        "gpt-4o", 0.5, 200, compat=True,
    )
    req = route.calls[0].request
    import json
    payload = json.loads(req.content)
    assert payload["model"] == "gpt-4o"
    assert payload["temperature"] == 0.5
    assert payload["max_tokens"] == 200
    assert len(payload["messages"]) == 2


@respx.mock
async def test_openai_auth_header(client):
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })
    )
    await client.ask(
        MESSAGES, "https://api.openai.com/v1", "sk-my-key",
        "gpt-4o", 0.3, 100, compat=True,
    )
    assert route.calls[0].request.headers["authorization"] == "Bearer sk-my-key"


@respx.mock
async def test_openai_no_auth_when_empty(client):
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })
    )
    await client.ask(
        MESSAGES, "https://api.openai.com/v1", "",
        "gpt-4o", 0.3, 100, compat=True,
    )
    assert "authorization" not in route.calls[0].request.headers


@respx.mock
async def test_openai_custom_headers(client):
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })
    )
    await client.ask(
        MESSAGES, "https://api.openai.com/v1", "sk-test",
        "gpt-4o", 0.3, 100, compat=True,
        custom_headers={"X-Title": "Bot"},
    )
    assert route.calls[0].request.headers["x-title"] == "Bot"


@respx.mock
@pytest.mark.parametrize("status", [400, 429, 500])
async def test_openai_error_status(client, status):
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(status, json={"error": "bad"})
    )
    with pytest.raises(RuntimeError, match=str(status)):
        await client.ask(
            MESSAGES, "https://api.openai.com/v1", "sk-test",
            "gpt-4o", 0.3, 100, compat=True,
        )


@respx.mock
async def test_openai_error_json_detail(client):
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(400, json={"error": {"message": "invalid model"}})
    )
    with pytest.raises(RuntimeError, match="invalid model"):
        await client.ask(
            MESSAGES, "https://api.openai.com/v1", "sk-test",
            "gpt-4o", 0.3, 100, compat=True,
        )


# ── Anthropic path ───────────────────────────────────────────────────────────

@respx.mock
async def test_anthropic_returns_text_and_body(client):
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(200, json={
            "content": [{"type": "text", "text": "Hi there"}],
        })
    )
    text, body = await client.ask(
        MESSAGES, "https://api.anthropic.com", "sk-ant-test",
        "claude-haiku", 0.3, 100, compat=False,
    )
    assert text == "Hi there"


@respx.mock
async def test_anthropic_extracts_system_message(client):
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(200, json={
            "content": [{"type": "text", "text": "ok"}],
        })
    )
    await client.ask(
        MESSAGES, "https://api.anthropic.com", "sk-ant",
        "claude-haiku", 0.3, 100, compat=False,
    )
    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload["system"] == "You are helpful."
    assert all(m["role"] != "system" for m in payload["messages"])


@respx.mock
async def test_anthropic_api_key_header(client):
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(200, json={
            "content": [{"type": "text", "text": "ok"}],
        })
    )
    await client.ask(
        MESSAGES, "https://api.anthropic.com", "sk-ant-key",
        "claude-haiku", 0.3, 100, compat=False,
    )
    assert route.calls[0].request.headers["x-api-key"] == "sk-ant-key"


@respx.mock
@pytest.mark.parametrize("status", [400, 500])
async def test_anthropic_error_status(client, status):
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(status, json={"error": "bad"})
    )
    with pytest.raises(RuntimeError, match=str(status)):
        await client.ask(
            MESSAGES, "https://api.anthropic.com", "sk-ant",
            "claude-haiku", 0.3, 100, compat=False,
        )
