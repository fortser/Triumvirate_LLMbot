"""Парсер ответов LLM → валидный шахматный ход (from, to, promotion).

Работает в двух режимах:
  - JSON-парсинг (json / json_thinking): ищет ТОЛЬКО ключи move_from / move_to
    в JSON-объекте. Не анализирует thinking и любой другой текст.
  - Текстовый (simple): regex-поиск координат в тексте ответа.

Поддерживает как серверную нотацию (A1-L12), так и Triumvirate (W3/B3.0, C/W.B).
Зависимости: только stdlib (re, json).
Зависимые: bot_runner.
"""
from __future__ import annotations

import json
import re
from typing import Any

# ─── Constants ────────────────────────────────────────────────────────────────
PROMO_MAP = {
    "q": "queen", "r": "rook", "b": "bishop", "n": "knight",
    # Triumvirate single-letter codes
    "m": "queen", "t": "rook", "d": "bishop",
    # "n" already maps to knight (Noctis)
}

# Server notation: A1, B12, L9, etc.
COORD_RE = re.compile(r"[A-La-l]\d{1,2}")

# Triumvirate notation: W3/B3.0 (7 chars) or C/W.B (5 chars)
TRI_COORD_RE = re.compile(
    r"(?:[WBR][123]/[WBR][0-3]\.[0-3]|C/[WBR]\.[WBR])"
)

# ─── JSON field names for the final move ──────────────────────────────────────
_MOVE_FROM_KEY = "move_from"
_MOVE_TO_KEY = "move_to"
_MOVE_PROMO_KEY = "promotion"

# Legacy keys (for backward compat)
_LEGACY_FROM_KEY = "from"
_LEGACY_TO_KEY = "to"

# ─── Control character sanitizer for broken JSON ─────────────────────────────
# Matches unescaped control chars (0x00-0x1F) inside JSON strings that should
# be escaped but aren't (common with Gemini, some DeepSeek outputs).
_CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def _sanitize_json_string(raw: str) -> str:
    """Fix common JSON issues from LLMs:
    1. Strip markdown ```json ... ``` wrappers.
    2. Escape unescaped control characters inside string values.
    3. Replace literal newlines/tabs inside JSON strings with \\n/\\t.
    """
    s = raw.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    if s.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1:]
        # Remove closing fence
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].rstrip()

    # Now fix control characters inside JSON string values.
    # Strategy: process character by character, tracking whether we're inside
    # a JSON string (between unescaped quotes).
    result = []
    in_string = False
    i = 0
    while i < len(s):
        ch = s[i]
        if in_string:
            if ch == '\\' and i + 1 < len(s):
                # Escaped character — keep as-is
                result.append(ch)
                result.append(s[i + 1])
                i += 2
                continue
            elif ch == '"':
                in_string = False
                result.append(ch)
            elif ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                result.append('\\r')
            elif ch == '\t':
                result.append('\\t')
            elif _CONTROL_CHAR_RE.match(ch):
                # Other control chars — unicode escape
                result.append(f'\\u{ord(ch):04x}')
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
            result.append(ch)
        i += 1

    return ''.join(result)


class MoveParser:
    """Parses and validates LLM response → (from, to, promotion) or None.

    For JSON formats (json / json_thinking):
        Only extracts move_from and move_to from the JSON object.
        Does NOT scan thinking text or any other field.
        If the move is illegal or keys are missing → returns None (triggers retry).

    For simple format:
        Scans the entire response text for coordinate pairs.
    """

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
            # STRICT: only look at JSON move keys, never fall through to text scan
            return self._from_json(text, legal_up, triumvirate)

        # simple format — text scan
        return self._from_text(text, legal_up, triumvirate)

    # ── piece-prefix strippers ────────────────────────────────────────────

    def _strip_piece_prefix(self, s: str) -> str:
        """Remove chess piece prefix for server notation (e.g. 'NE2' → 'E2')."""
        if len(s) >= 3 and s[0] in "NBRQKP" and COORD_RE.match(s[1:]):
            return s[1:]
        return s

    def _strip_piece_prefix_tri(self, s: str) -> str:
        """Remove piece prefix for Triumvirate (e.g. 'PW3/B2.0' or 'P:W3/B2.0' → 'W3/B2.0')."""
        # With colon separator: L:W3/R3.3 → W3/R3.3
        if len(s) >= 7 and s[0] in "LMTDNP" and s[1] == ":" and TRI_COORD_RE.match(s[2:]):
            return s[2:]
        # Without separator (legacy): PW3/B2.0 → W3/B2.0
        if (
            len(s) >= 6
            and s[0] in "LMTDNP"
            and s[0] not in "WBR"
            and TRI_COORD_RE.match(s[1:])
        ):
            return s[1:]
        return s

    # ── JSON mode (STRICT) ────────────────────────────────────────────────

    def _from_json(
        self, text: str, legal_up: dict, triumvirate: bool
    ) -> tuple[str, str, str | None] | None:
        """Extract move ONLY from JSON move_from / move_to keys.

        Applies sanitization to handle common LLM JSON quirks:
        - Markdown code fences
        - Unescaped newlines/control chars in string values
        """
        sanitized = _sanitize_json_string(text)

        s = sanitized.find("{")
        e = sanitized.rfind("}")
        if s == -1 or e <= s:
            return None
        try:
            obj = json.loads(sanitized[s : e + 1])
        except json.JSONDecodeError:
            return None

        # Try new unique keys first, fall back to legacy keys
        raw_f = str(
            obj.get(_MOVE_FROM_KEY) or obj.get(_LEGACY_FROM_KEY) or ""
        ).strip()
        raw_t = str(
            obj.get(_MOVE_TO_KEY) or obj.get(_LEGACY_TO_KEY) or ""
        ).strip()

        if not raw_f or not raw_t:
            return None

        if triumvirate:
            f = self._strip_piece_prefix_tri(raw_f.upper())
            t = self._strip_piece_prefix_tri(raw_t.upper())
        else:
            f = self._strip_piece_prefix(raw_f.upper())
            t = self._strip_piece_prefix(raw_t.upper())

        promo = self._norm_promo(obj.get(_MOVE_PROMO_KEY))

        # STRICT validation — if illegal, return None (no text fallback)
        return self._validate(f, t, promo, legal_up)

    # ── Text mode (only for 'simple' format) ──────────────────────────────

    def _from_text(
        self, text: str, legal_up: dict, triumvirate: bool
    ) -> tuple[str, str, str | None] | None:
        upper = text.upper()

        promo = None
        m = re.search(r"=([QRBNMTD])", upper)
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
        # Triumvirate piece names → server API names
        _TRI_PROMO = {
            "marshal": "queen", "train": "rook",
            "drone": "bishop", "noctis": "knight",
        }
        if s in _TRI_PROMO:
            return _TRI_PROMO[s]
        return PROMO_MAP.get(s)
