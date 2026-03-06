"""Парсер ответов LLM → валидный шахматный ход (from, to, promotion).

Работает в двух режимах: JSON-парсинг и текстовый (regex).
Зависимости: только stdlib (re, json).
Зависимые: bot_runner.
"""
from __future__ import annotations

import json
import re
from typing import Any

# ─── Constants (used only in this module) ─────────────────────────────────────
PROMO_MAP = {"q": "queen", "r": "rook", "b": "bishop", "n": "knight"}
COORD_RE = re.compile(r"[A-La-l]\d{1,2}")


class MoveParser:
    """Parses and validates LLM response → (from, to, promotion) or None."""

    def parse(
        self, text: str, legal: dict, fmt: str
    ) -> tuple[str, str, str | None] | None:
        legal_up = {k.upper(): [v.upper() for v in vs] for k, vs in legal.items()}

        if fmt in ("json", "json_thinking"):
            result = self._from_json(text, legal_up)
            if result:
                return result

        return self._from_text(text, legal_up)

    def _strip_piece_prefix(self, s: str) -> str:
        if len(s) >= 3 and s[0] in "NBRQKP" and COORD_RE.match(s[1:]):
            return s[1:]
        return s

    def _from_json(
        self, text: str, legal_up: dict
    ) -> tuple[str, str, str | None] | None:
        s = text.find("{")
        e = text.rfind("}")
        if s == -1 or e <= s:
            return None
        try:
            obj = json.loads(text[s : e + 1])
        except json.JSONDecodeError:
            return None
        f = self._strip_piece_prefix(str(obj.get("from", "")).upper().strip())
        t = self._strip_piece_prefix(str(obj.get("to", "")).upper().strip())
        if not f or not t:
            return None
        promo = self._norm_promo(obj.get("promotion"))
        return self._validate(f, t, promo, legal_up)

    def _from_text(
        self, text: str, legal_up: dict
    ) -> tuple[str, str, str | None] | None:
        upper = text.upper()
        coords = COORD_RE.findall(upper)
        promo = None
        m = re.search(r"=([QRBN])", upper)
        if m:
            promo = PROMO_MAP.get(m.group(1).lower())

        for i in range(len(coords) - 1):
            f, t = coords[i].upper(), coords[i + 1].upper()
            if f == t:
                continue
            result = self._validate(f, t, promo, legal_up)
            if result:
                return result

        return None

    def _validate(
        self, f: str, t: str, promo: str | None, legal_up: dict
    ) -> tuple[str, str, str | None] | None:
        if f in legal_up and t in legal_up[f]:
            return (f, t, promo)
        return None

    def _norm_promo(self, raw: Any) -> str | None:
        if raw is None:
            return None
        s = str(raw).lower().strip()
        if s in ("queen", "rook", "bishop", "knight"):
            return s
        return PROMO_MAP.get(s)
