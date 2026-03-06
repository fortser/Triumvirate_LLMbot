"""Парсер ответов LLM → валидный шахматный ход (from, to, promotion).

Работает в двух режимах: JSON-парсинг и текстовый (regex).
Поддерживает как серверную нотацию (A1-L12), так и Triumvirate (W3/B3.0, C/W.B).
Зависимости: только stdlib (re, json).
Зависимые: bot_runner.
"""
from __future__ import annotations

import json
import re
from typing import Any

# ─── Constants ────────────────────────────────────────────────────────────────
PROMO_MAP = {"q": "queen", "r": "rook", "b": "bishop", "n": "knight"}

# Server notation: A1, B12, L9, etc.
COORD_RE = re.compile(r"[A-La-l]\d{1,2}")

# Triumvirate notation: W3/B3.0 (7 chars) or C/W.B (5 chars)
TRI_COORD_RE = re.compile(
    r"(?:[WBR][123]/[WBR][0-3]\.[0-3]|C/[WBR]\.[WBR])"
)


class MoveParser:
    """Parses and validates LLM response → (from, to, promotion) or None."""

    def parse(
        self,
        text: str,
        legal: dict,
        fmt: str,
        triumvirate: bool = False,
    ) -> tuple[str, str, str | None] | None:
        """Parse LLM response and validate against legal moves.

        Args:
            text: raw LLM response text.
            legal: legal moves dict (already in Triumvirate if triumvirate=True).
            fmt: response format ('simple', 'json', 'json_thinking').
            triumvirate: if True, parse Triumvirate notation instead of server.

        Returns:
            (from, to, promotion) in the same notation as ``legal``, or None.
        """
        legal_up = {
            k.upper(): [v.upper() for v in vs] for k, vs in legal.items()
        }

        if fmt in ("json", "json_thinking"):
            result = self._from_json(text, legal_up, triumvirate)
            if result:
                return result

        return self._from_text(text, legal_up, triumvirate)

    # ── piece-prefix strippers ────────────────────────────────────────────

    def _strip_piece_prefix(self, s: str) -> str:
        """Remove chess piece prefix for server notation (e.g. 'NE2' → 'E2')."""
        if len(s) >= 3 and s[0] in "NBRQKP" and COORD_RE.match(s[1:]):
            return s[1:]
        return s

    def _strip_piece_prefix_tri(self, s: str) -> str:
        """Remove piece prefix for Triumvirate (e.g. 'PW3/B2.0' → 'W3/B2.0').

        Triumvirate coords start with W/B/R/C — only strip if prefix letter
        is NOT one of those and the remainder matches a Triumvirate coordinate.
        Also handles Triumvirate piece symbols: L M T D N P.
        """
        if (
            len(s) >= 6
            and s[0] in "LMTDNP"
            and s[0] not in "WBR"
            and TRI_COORD_RE.match(s[1:])
        ):
            return s[1:]
        return s

    # ── JSON mode ─────────────────────────────────────────────────────────

    def _from_json(
        self, text: str, legal_up: dict, triumvirate: bool
    ) -> tuple[str, str, str | None] | None:
        s = text.find("{")
        e = text.rfind("}")
        if s == -1 or e <= s:
            return None
        try:
            obj = json.loads(text[s : e + 1])
        except json.JSONDecodeError:
            return None

        raw_f = str(obj.get("from", "")).strip()
        raw_t = str(obj.get("to", "")).strip()
        if not raw_f or not raw_t:
            return None

        if triumvirate:
            f = self._strip_piece_prefix_tri(raw_f.upper())
            t = self._strip_piece_prefix_tri(raw_t.upper())
        else:
            f = self._strip_piece_prefix(raw_f.upper())
            t = self._strip_piece_prefix(raw_t.upper())

        promo = self._norm_promo(obj.get("promotion"))
        return self._validate(f, t, promo, legal_up)

    # ── Text mode ─────────────────────────────────────────────────────────

    def _from_text(
        self, text: str, legal_up: dict, triumvirate: bool
    ) -> tuple[str, str, str | None] | None:
        upper = text.upper()

        promo = None
        m = re.search(r"=([QRBN])", upper)
        if m:
            promo = PROMO_MAP.get(m.group(1).lower())

        coord_re = TRI_COORD_RE if triumvirate else COORD_RE
        coords = coord_re.findall(upper)

        for i in range(len(coords) - 1):
            f, t = coords[i].upper(), coords[i + 1].upper()
            if f == t:
                continue
            result = self._validate(f, t, promo, legal_up)
            if result:
                return result

        return None

    # ── Validation ────────────────────────────────────────────────────────

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
