"""HTTP-клиент для LLM-провайдеров (OpenAI-compatible + Anthropic native).

Зависимости: httpx.
Зависимые: bot_runner.
"""
from __future__ import annotations

from typing import Any

import httpx


class LLMClient:
    """Sends chat requests to LLM providers.

    Returns a tuple of (response_text, full_response_body) so that callers
    can inspect usage / cost fields from the raw API response.
    """

    async def ask(
        self,
        messages: list[dict],
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        compat: bool,
        custom_headers: dict | None = None,
        timeout: int = 120,
    ) -> tuple[str, dict]:
        """Returns (text, full_response_body)."""
        if compat:
            return await self._openai(
                messages, base_url, api_key, model,
                temperature, max_tokens, custom_headers or {}, timeout,
            )
        return await self._anthropic(
            messages, base_url, api_key, model, temperature, max_tokens, timeout
        )

    async def _openai(
        self,
        messages: list[dict],
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        custom_headers: dict,
        timeout: int,
    ) -> tuple[str, dict]:
        url = base_url.rstrip("/") + "/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(custom_headers)
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, json=body, headers=headers)
            if r.status_code >= 400:
                try:
                    detail = r.json()
                except Exception:
                    detail = r.text[:300]
                raise RuntimeError(
                    f"{r.status_code} {r.reason_phrase}: {detail}"
                )
            resp_body = r.json()
            text = resp_body["choices"][0]["message"]["content"] or ""
            return text, resp_body

    async def _anthropic(
        self,
        messages: list[dict],
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> tuple[str, dict]:
        system = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_msgs.append(m)
        url = base_url.rstrip("/") + "/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        body: dict[str, Any] = {
            "model": model,
            "messages": user_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, json=body, headers=headers)
            if r.status_code >= 400:
                try:
                    detail = r.json()
                except Exception:
                    detail = r.text[:300]
                raise RuntimeError(
                    f"{r.status_code} {r.reason_phrase}: {detail}"
                )
            resp_body = r.json()
            text = resp_body["content"][0]["text"]
            return text, resp_body
