"""Tests for bot_runner.py — BotRunner game loop orchestration."""
from __future__ import annotations

import asyncio

import pytest
import respx
from httpx import Response

import settings as settings_module
from bot_runner import BotRunner
from settings import Settings


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "_HERE", tmp_path)
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(Settings, "_file", tmp_path / "settings.json")

    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "system_prompt.txt").write_text("You are a chess engine.", encoding="utf-8")
    (prompts / "user_prompt_template.txt").write_text(
        "Move #{{move_number}} | You are {{current_player}}\n"
        "Legal: {{legal_moves}}\nLast: {{last_move}}\n{{check}}\nBoard:\n{{board}}",
        encoding="utf-8",
    )
    (prompts / "format_json.txt").write_text("Respond with JSON.", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def logs():
    return []


@pytest.fixture()
def runner(isolated_settings, logs, tmp_path):
    s = Settings()
    s._d["response_format"] = "json"
    s._d["max_retries"] = 3
    s._d["temperature"] = 0.3
    s._d["model"] = "test-model"
    s._d["base_url"] = "https://llm.test/v1"
    s._d["api_key"] = "test-key"
    s._d["compat"] = True

    def noop(*a, **kw):
        pass

    r = BotRunner(s, on_log=lambda msg: logs.append(msg), on_status=noop, on_state=noop)
    r.tracer = __import__("tracer").MoveTracer(tmp_path / "test_logs")
    r.pricing.set_zero()
    return r


LEGAL = {"A2": ["A3", "A4"], "E2": ["E3", "E4"]}
STATE = {
    "move_number": 1,
    "current_player": "white",
    "game_status": "playing",
    "legal_moves": LEGAL,
    "board": [{"notation": "A2", "color": "white", "type": "pawn", "owner": "white"}],
    "players": [{"color": "white", "status": "active"}],
    "last_move": None,
    "check": None,
    "position_3pf": "start",
}


# ── _detect_openrouter ──────────────────────────────────────────────────────

def test_detect_openrouter_by_provider(runner):
    runner.s._d["provider"] = "OpenRouter"
    runner.s._d["base_url"] = "https://example.com/v1"
    assert runner._detect_openrouter() is True


def test_detect_openrouter_by_url(runner):
    runner.s._d["provider"] = "Custom"
    runner.s._d["base_url"] = "https://openrouter.ai/api/v1"
    assert runner._detect_openrouter() is True


def test_detect_openrouter_false(runner):
    runner.s._d["provider"] = "OpenAI API"
    runner.s._d["base_url"] = "https://api.openai.com/v1"
    assert runner._detect_openrouter() is False


# ── _choose_move ─────────────────────────────────────────────────────────────

@respx.mock
async def test_choose_move_success(runner):
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": '{"move_from":"A2","move_to":"A4"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
    )
    runner.tracer.init("g1", 1, "test")
    result = await runner._choose_move(STATE, LEGAL)
    assert result == ("A2", "A4", None)


@respx.mock
async def test_choose_move_promotion(runner):
    legal = {"A7": ["A8"]}
    state = {**STATE, "legal_moves": legal}
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": '{"move_from":"A7","move_to":"A8","promotion":"queen"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
    )
    runner.tracer.init("g1", 1, "test")
    result = await runner._choose_move(state, legal)
    assert result == ("A7", "A8", "queen")


@respx.mock
async def test_choose_move_retry_on_bad_response(runner):
    route = respx.post("https://llm.test/v1/chat/completions")
    route.side_effect = [
        Response(200, json={
            "choices": [{"message": {"content": '{"thinking":"hmm"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }),
        Response(200, json={
            "choices": [{"message": {"content": '{"move_from":"A2","move_to":"A3"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }),
    ]
    runner.tracer.init("g1", 1, "test")
    result = await runner._choose_move(STATE, LEGAL)
    assert result == ("A2", "A3", None)
    assert route.call_count == 2


@respx.mock
async def test_choose_move_all_retries_exhausted(runner):
    runner.s._d["max_retries"] = 2
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "I dont know"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        })
    )
    runner.tracer.init("g1", 1, "test")
    result = await runner._choose_move(STATE, LEGAL)
    assert result is None


@respx.mock
async def test_choose_move_temperature_escalation(runner):
    runner.s._d["temperature"] = 0.3
    runner.s._d["max_retries"] = 3
    calls = []

    def capture_request(request):
        import json
        payload = json.loads(request.content)
        calls.append(payload["temperature"])
        return Response(200, json={
            "choices": [{"message": {"content": "bad"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        })

    respx.post("https://llm.test/v1/chat/completions").mock(side_effect=capture_request)
    runner.tracer.init("g1", 1, "test")
    await runner._choose_move(STATE, LEGAL)
    # Temperature should increase: 0.3, 0.5, 0.7
    assert calls[0] == pytest.approx(0.3)
    assert calls[1] > calls[0]
    assert calls[2] > calls[1]


@respx.mock
async def test_choose_move_retry_hint_json(runner, logs):
    runner.s._d["max_retries"] = 2
    runner.s._d["response_format"] = "json"
    calls = []

    def capture(request):
        import json
        payload = json.loads(request.content)
        calls.append(payload["messages"])
        return Response(200, json={
            "choices": [{"message": {"content": "bad"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        })

    respx.post("https://llm.test/v1/chat/completions").mock(side_effect=capture)
    runner.tracer.init("g1", 1, "test")
    await runner._choose_move(STATE, LEGAL)
    # Second attempt should have retry hint
    assert "REMINDER" in calls[1][1]["content"]
    assert "move_from" in calls[1][1]["content"]


@respx.mock
async def test_choose_move_retry_hint_simple(runner, logs):
    runner.s._d["max_retries"] = 2
    runner.s._d["response_format"] = "simple"
    calls = []

    def capture(request):
        import json
        payload = json.loads(request.content)
        calls.append(payload["messages"])
        return Response(200, json={
            "choices": [{"message": {"content": "I like chess"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        })

    respx.post("https://llm.test/v1/chat/completions").mock(side_effect=capture)
    runner.tracer.init("g1", 1, "test")
    await runner._choose_move(STATE, LEGAL)
    assert "FROM TO" in calls[1][1]["content"]


# ── Stats tracking ───────────────────────────────────────────────────────────

@respx.mock
async def test_stats_after_choose_move(runner):
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": '{"move_from":"A2","move_to":"A4"}'}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        })
    )
    runner.tracer.init("g1", 1, "test")
    await runner._choose_move(STATE, LEGAL)
    assert runner.stats["llm_calls"] == 1


@respx.mock
async def test_stats_tokens_accumulated(runner):
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": '{"move_from":"A2","move_to":"A4"}'}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        })
    )
    runner.tracer.init("g1", 1, "test")
    await runner._choose_move(STATE, LEGAL)
    assert runner.stats["total_prompt_tokens"] == 50
    assert runner.stats["total_completion_tokens"] == 20
    assert runner.stats["total_tokens"] == 70


# ── Lifecycle ────────────────────────────────────────────────────────────────

@respx.mock
async def test_start_sets_running(runner):
    # Mock everything so _run doesn't make real requests
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    runner.start()
    assert runner._running is True
    runner.stop()
    await asyncio.sleep(0.05)


@respx.mock
async def test_stop_clears_running(runner):
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    runner.start()
    runner.stop()
    assert runner._running is False
    await asyncio.sleep(0.05)


@respx.mock
async def test_start_when_already_running_noop(runner):
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    runner.start()
    task1 = runner._task
    runner.start()  # should be noop
    assert runner._task is task1
    runner.stop()
    await asyncio.sleep(0.05)
