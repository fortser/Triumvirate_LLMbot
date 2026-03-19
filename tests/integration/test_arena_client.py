"""Tests for arena_client.py — ArenaClient HTTP requests via respx."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from arena_client import ArenaClient

BASE = "https://arena.example.com"


@pytest.fixture()
def ac():
    return ArenaClient(BASE)


def test_constructor_builds_url():
    ac = ArenaClient("https://arena.example.com/")
    assert ac._base == "https://arena.example.com/api/v1"


def test_constructor_strips_trailing_slash():
    ac = ArenaClient("https://arena.example.com/")
    assert not ac._base.endswith("/api/v1/")


@respx.mock
async def test_join_stores_token_game_id_color(ac):
    respx.post(f"{BASE}/api/v1/join").mock(
        return_value=Response(200, json={
            "player_token": "tok-abc",
            "game_id": "game-123",
            "color": "white",
            "status": "waiting",
        })
    )
    data = await ac.join("TestBot")
    assert ac.token == "tok-abc"
    assert ac.game_id == "game-123"
    assert ac.color == "white"


@respx.mock
async def test_join_with_model(ac):
    route = respx.post(f"{BASE}/api/v1/join").mock(
        return_value=Response(200, json={
            "player_token": "t", "game_id": "g", "color": "black", "status": "ok",
        })
    )
    await ac.join("Bot", model="gpt-4o")
    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload["model"] == "gpt-4o"


@respx.mock
async def test_get_state_sends_auth_header(ac):
    ac.token = "tok-xyz"
    route = respx.get(f"{BASE}/api/v1/state").mock(
        return_value=Response(200, json={"game_status": "playing"})
    )
    await ac.get_state()
    assert route.calls[0].request.headers["authorization"] == "Bearer tok-xyz"


@respx.mock
async def test_make_move_returns_status_and_data(ac):
    ac.token = "tok"
    respx.post(f"{BASE}/api/v1/move").mock(
        return_value=Response(200, json={"status": "ok"})
    )
    code, data = await ac.make_move("A2", "A4", 1)
    assert code == 200
    assert data["status"] == "ok"


@respx.mock
async def test_make_move_with_promotion(ac):
    ac.token = "tok"
    route = respx.post(f"{BASE}/api/v1/move").mock(
        return_value=Response(200, json={"status": "ok"})
    )
    await ac.make_move("A7", "A8", 5, promotion="queen")
    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload["promotion"] == "queen"


@respx.mock
async def test_make_move_non_json_response(ac):
    ac.token = "tok"
    respx.post(f"{BASE}/api/v1/move").mock(
        return_value=Response(500, text="Internal Server Error")
    )
    code, data = await ac.make_move("A2", "A4", 1)
    assert code == 500
    assert isinstance(data, str)


@respx.mock
async def test_health_returns_dict(ac):
    respx.get(f"{BASE}/api/v1/health").mock(
        return_value=Response(200, json={"status": "ok", "active_games": 3})
    )
    result = await ac.health()
    assert result["status"] == "ok"


@respx.mock
async def test_resign_correct_endpoint(ac):
    ac.token = "tok"
    route = respx.post(f"{BASE}/api/v1/resign").mock(
        return_value=Response(200, json={"game_status": "finished"})
    )
    result = await ac.resign()
    assert route.calls[0].request.url.path == "/api/v1/resign"
    assert result["game_status"] == "finished"


@respx.mock
async def test_skip_waiting_correct_endpoint(ac):
    ac.token = "tok"
    route = respx.post(f"{BASE}/api/v1/skip-waiting").mock(
        return_value=Response(200, json={"ok": True})
    )
    await ac.skip_waiting()
    assert route.calls[0].request.url.path == "/api/v1/skip-waiting"


@respx.mock
async def test_list_games_returns_list(ac):
    respx.get(f"{BASE}/api/v1/games").mock(
        return_value=Response(200, json=[
            {"game_id": "g1", "players": []},
            {"game_id": "g2", "players": []},
        ])
    )
    result = await ac.list_games()
    assert len(result) == 2
