"""Observability-слой: полный trace каждого хода → JSON-файл.

Собирает: сырой стейт, промпт, все LLM-запросы/ответы с usage/cost,
парсинг, выбранный ход, ответ сервера. Сохраняет в logs/game_<id>/move_NNN.json.

Зависимости: только stdlib (pathlib, json, time, re).
Зависимые: bot_runner.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


class MoveTracer:
    """Collects full pipeline trace for one move.

    v2.1: includes per-attempt token usage, cost breakdown, and model pricing.
    """

    def __init__(self, logs_dir: Path) -> None:
        self._logs_dir = logs_dir
        self._data: dict[str, Any] = {}
        self._move_start: float = 0.0
        self._llm_time_total: float = 0.0
        self._model: str = "unknown_model"

    def init(self, game_id: str, move_number: int, model: str = "") -> None:
        self._model = (
            re.sub(r'[\\/:*?"<>|]', "_", model).strip("_") if model else "unknown_model"
        )
        self._data = {
            "game_id": game_id,
            "move_number": move_number,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "outcome": "unknown",
            "model_pricing": {},
            "server_interactions": [],
            "server_state_raw": {},
            "prompt_pipeline": {},
            "llm_requests": [],
            "llm_responses": [],
            "parser_attempts": [],
            "move_selected": None,
            "server_move_request": {},
            "server_move_response": {},
            "statistics": {},
        }
        self._move_start = time.time()
        self._llm_time_total = 0.0

    def set_model_pricing(self, pricing: dict) -> None:
        self._data["model_pricing"] = pricing

    def add_server_interaction(
        self, endpoint: str, method: str, response_raw: Any
    ) -> None:
        self._data["server_interactions"].append(
            {"endpoint": endpoint, "method": method, "response_raw": response_raw}
        )

    def set_outcome(self, outcome: str) -> None:
        self._data["outcome"] = outcome

    def set_server_state_raw(self, state: dict) -> None:
        self._data["server_state_raw"] = state

    def set_prompt_pipeline(self, pipeline: dict) -> None:
        self._data["prompt_pipeline"] = pipeline

    def add_llm_request(self, attempt: int, messages: list) -> None:
        self._data["llm_requests"].append({"attempt": attempt, "messages": messages})

    def add_llm_response(
        self,
        attempt: int,
        raw: str,
        chars: int,
        time_sec: float,
        usage: dict | None = None,
        cost: dict | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "attempt": attempt,
            "raw_response": raw,
            "response_chars": chars,
            "time_sec": round(time_sec, 3),
        }
        if usage is not None:
            entry["usage"] = usage
        if cost is not None:
            entry["cost"] = cost
        self._data["llm_responses"].append(entry)
        self._llm_time_total += time_sec

    def add_parser_attempt(
        self, attempt: int, coords_found: list, pairs_tested: list, valid: bool
    ) -> None:
        self._data["parser_attempts"].append(
            {
                "attempt": attempt,
                "coordinates_found": coords_found,
                "pairs_tested": pairs_tested,
                "valid": valid,
            }
        )

    def set_move_selected(self, from_sq: str, to_sq: str, promo: str | None) -> None:
        self._data["move_selected"] = {"from": from_sq, "to": to_sq, "promotion": promo}

    def set_server_move_request(self, req: dict) -> None:
        self._data["server_move_request"] = req

    def set_server_move_response(self, status_code: int, data: Any) -> None:
        self._data["server_move_response"] = {"status_code": status_code, "data": data}

    def finalize_statistics(self) -> None:
        llm_reqs = self._data.get("llm_requests", [])
        llm_resp = self._data.get("llm_responses", [])
        total_prompt_chars = sum(
            sum(len(m.get("content", "")) for m in req["messages"]) for req in llm_reqs
        )
        total_resp_chars = sum(r["response_chars"] for r in llm_resp)

        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_reasoning_tokens = 0
        total_all_tokens = 0
        total_cost_usd = 0.0
        total_provider_cost_usd: float | None = None

        for r in llm_resp:
            usage = r.get("usage") or {}
            total_prompt_tokens += usage.get("prompt_tokens", 0)
            total_completion_tokens += usage.get("completion_tokens", 0)
            total_reasoning_tokens += usage.get("reasoning_tokens", 0)
            total_all_tokens += usage.get("total_tokens", 0)

            cost = r.get("cost") or {}
            total_cost_usd += cost.get("total_cost_usd", 0.0)

            prc = usage.get("provider_reported_cost_usd")
            if prc is not None:
                if total_provider_cost_usd is None:
                    total_provider_cost_usd = 0.0
                total_provider_cost_usd += prc

        self._data["statistics"] = {
            "time_total_sec": round(time.time() - self._move_start, 3),
            "llm_time_sec": round(self._llm_time_total, 3),
            "prompt_chars": total_prompt_chars,
            "response_chars": total_resp_chars,
            "total_llm_chars": total_prompt_chars + total_resp_chars,
            "llm_calls": len(llm_resp),
            "retries": max(0, len(llm_resp) - 1),
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_reasoning_tokens": total_reasoning_tokens,
            "total_tokens": total_all_tokens,
            "total_cost_usd": round(total_cost_usd, 8),
            "provider_reported_cost_usd": (
                round(total_provider_cost_usd, 8)
                if total_provider_cost_usd is not None
                else None
            ),
            "model_pricing": self._data.get("model_pricing", {}),
        }

    def save(self) -> None:
        if not self._data:
            return
        game_id = self._data.get("game_id", "unknown")
        move_num = self._data.get("move_number", 0)
        game_dir = self._logs_dir / f"game_{game_id}__{self._model}"
        try:
            game_dir.mkdir(parents=True, exist_ok=True)
            path = game_dir / f"move_{move_num:03d}.json"
            path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass
