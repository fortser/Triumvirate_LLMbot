"""HTTP-клиент для REST API шахматной арены Triumvirate.

Зависимости: httpx.
Зависимые: bot_runner.
"""
from __future__ import annotations

from typing import Any

import httpx


class ArenaClient:
    """HTTP client for the Triumvirate Arena REST API."""

    def __init__(self, server_url: str) -> None:
        self._base = server_url.rstrip("/") + "/api/v1"
        self.token: str | None = None
        self.game_id: str | None = None
        self.color: str | None = None

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/health")
            r.raise_for_status()
            return r.json()

    async def join(self, name: str, model: str = "") -> dict:
        body: dict[str, Any] = {"name": name, "type": "llm"}
        if model:
            body["model"] = model
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self._base}/join", json=body)
            r.raise_for_status()
            data = r.json()
        self.token = data["player_token"]
        self.game_id = data["game_id"]
        self.color = data["color"]
        return data

    async def get_state(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{self._base}/state", headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def make_move(
        self, from_sq: str, to_sq: str, move_number: int,
        promotion: str | None = None, message: str | None = None,
    ) -> tuple[int, Any]:
        body: dict[str, Any] = {"from": from_sq, "to": to_sq, "move_number": move_number}
        if promotion:
            body["promotion"] = promotion
        if message and message.strip():
            body["message"] = message.strip()
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self._base}/move", json=body, headers=self._headers)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return r.status_code, data

    async def skip_waiting(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self._base}/skip-waiting", headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def resign(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self._base}/resign", headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def list_games(self) -> list:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/games")
            r.raise_for_status()
            return r.json()
