"""Tests for tracer.py — MoveTracer JSON trace recording."""
from __future__ import annotations

import json

import pytest

from tracer import MoveTracer


@pytest.fixture()
def tracer(tmp_path):
    return MoveTracer(tmp_path)


def test_init_sets_fields(tracer):
    tracer.init("game-123", 1, "gpt-4o")
    assert tracer._data["game_id"] == "game-123"
    assert tracer._data["move_number"] == 1
    assert tracer._model == "gpt-4o"


def test_init_sanitizes_model_name(tracer):
    tracer.init("g1", 1, 'model/with:bad*chars?"<>|')
    assert "/" not in tracer._model
    assert ":" not in tracer._model
    assert "*" not in tracer._model


def test_add_llm_response_accumulates(tracer):
    tracer.init("g1", 1)
    tracer.add_llm_response(1, "resp1", 100, 1.5)
    tracer.add_llm_response(2, "resp2", 200, 2.0)
    assert len(tracer._data["llm_responses"]) == 2


def test_add_llm_response_with_usage_and_cost(tracer):
    tracer.init("g1", 1)
    usage = {"prompt_tokens": 10, "completion_tokens": 20}
    cost = {"total_cost_usd": 0.001}
    tracer.add_llm_response(1, "resp", 50, 1.0, usage=usage, cost=cost)
    entry = tracer._data["llm_responses"][0]
    assert entry["usage"] == usage
    assert entry["cost"] == cost


def test_finalize_statistics_sums_correctly(tracer):
    tracer.init("g1", 1)
    tracer.add_llm_request(1, [{"role": "user", "content": "hello"}])
    tracer.add_llm_response(
        1, "world", 5, 1.0,
        usage={"prompt_tokens": 10, "completion_tokens": 20,
               "reasoning_tokens": 5, "total_tokens": 35},
        cost={"total_cost_usd": 0.001},
    )
    tracer.finalize_statistics()
    stats = tracer._data["statistics"]
    assert stats["total_prompt_tokens"] == 10
    assert stats["total_completion_tokens"] == 20
    assert stats["total_reasoning_tokens"] == 5
    assert stats["llm_calls"] == 1
    assert stats["retries"] == 0


def test_finalize_statistics_retries_count(tracer):
    tracer.init("g1", 1)
    for i in range(3):
        tracer.add_llm_request(i + 1, [{"role": "user", "content": "hi"}])
        tracer.add_llm_response(i + 1, "resp", 4, 0.5)
    tracer.finalize_statistics()
    assert tracer._data["statistics"]["retries"] == 2


def test_finalize_statistics_provider_cost_accumulates(tracer):
    tracer.init("g1", 1)
    tracer.add_llm_response(
        1, "r", 1, 0.1,
        usage={"prompt_tokens": 0, "completion_tokens": 0,
               "reasoning_tokens": 0, "total_tokens": 0,
               "provider_reported_cost_usd": 0.005},
    )
    tracer.add_llm_response(
        2, "r", 1, 0.1,
        usage={"prompt_tokens": 0, "completion_tokens": 0,
               "reasoning_tokens": 0, "total_tokens": 0,
               "provider_reported_cost_usd": 0.003},
    )
    tracer.finalize_statistics()
    assert tracer._data["statistics"]["provider_reported_cost_usd"] == pytest.approx(0.008)


def test_finalize_statistics_provider_cost_none(tracer):
    tracer.init("g1", 1)
    tracer.add_llm_response(1, "r", 1, 0.1)
    tracer.finalize_statistics()
    assert tracer._data["statistics"]["provider_reported_cost_usd"] is None


def test_save_creates_dir_and_file(tracer, tmp_path):
    tracer.init("abc-123", 5, "test-model")
    tracer.set_outcome("success")
    tracer.finalize_statistics()
    tracer.save()

    game_dir = tmp_path / "game_abc-123__test-model"
    assert game_dir.exists()
    move_file = game_dir / "move_005.json"
    assert move_file.exists()
    data = json.loads(move_file.read_text(encoding="utf-8"))
    assert data["game_id"] == "abc-123"
    assert data["outcome"] == "success"


def test_save_empty_data_skipped(tracer, tmp_path):
    tracer.save()
    # No files should be created
    assert list(tmp_path.iterdir()) == []


def test_full_trace_cycle(tracer, tmp_path):
    tracer.init("g1", 1, "model-x")
    tracer.set_model_pricing({"prompt_per_1m_usd": 1.0, "source": "test"})
    tracer.set_server_state_raw({"game_status": "playing"})
    tracer.set_prompt_pipeline({"system": "...", "user": "..."})
    tracer.add_llm_request(1, [{"role": "user", "content": "make a move"}])
    tracer.add_llm_response(1, '{"move_from":"A2","move_to":"A4"}', 35, 1.2)
    tracer.add_parser_attempt(1, ["A2", "A4"], ["A2->A4(OK)"], True)
    tracer.set_move_selected("A2", "A4", None)
    tracer.set_server_move_request({"from": "A2", "to": "A4"})
    tracer.set_server_move_response(200, {"status": "ok"})
    tracer.set_outcome("success")
    tracer.finalize_statistics()
    tracer.save()

    files = list((tmp_path / "game_g1__model-x").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["outcome"] == "success"
    assert data["move_selected"]["from"] == "A2"
