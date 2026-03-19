"""notation_converter.py — Конвертер серверной нотации ↔ TRIUMVIRATE v4.0.

Серверная нотация: буква (A-L) + цифра (1-12), например A1, E4, L12.
TRIUMVIRATE v4.0:  радиально-кольцевая нотация, например W3/B3.0, C/W.B.

Портировано из серверного модуля board/triumvirate_notation.py.
Конвертер полностью автономен — не зависит от серверного проекта.
Все 96 записей предвычислены при импорте модуля, O(1) lookup.
"""

from __future__ import annotations

from typing import Any

# ═══════════════════════════════════════════════════════════════════
# КОНСТАНТЫ МАППИНГА
# ═══════════════════════════════════════════════════════════════════

_COLUMN_ORDER: dict[str, tuple[str, ...]] = {
    "W": ("A", "B", "C", "D", "E", "F", "G", "H"),
    "B": ("A", "B", "C", "D", "I", "J", "K", "L"),
    "R": ("H", "G", "F", "E", "I", "J", "K", "L"),
}

_ROW_ORDER: dict[str, tuple[int, ...]] = {
    "W": (1, 2, 3, 4),
    "B": (8, 7, 6, 5),
    "R": (12, 11, 10, 9),
}

_CW_NEIGHBOR: dict[str, str] = {"W": "B", "B": "R", "R": "W"}
_CCW_NEIGHBOR: dict[str, str] = {"W": "R", "B": "W", "R": "B"}


# ═══════════════════════════════════════════════════════════════════
# ПОСТРОЕНИЕ ТАБЛИЦ
# ═══════════════════════════════════════════════════════════════════


def _compute_notation(sector: str, game_col: int, game_row: int) -> str:
    """Вычисляет нотацию TRIUMVIRATE v4.0 из игровых координат."""
    if game_row == 4 and game_col in (4, 5):
        neighbor = (
            _CW_NEIGHBOR[sector] if game_col == 4 else _CCW_NEIGHBOR[sector]
        )
        return f"C/{sector}.{neighbor}"

    if game_col <= 4:
        opponent = _CW_NEIGHBOR[sector]
        flank = game_col - 1
    else:
        opponent = _CCW_NEIGHBOR[sector]
        flank = 8 - game_col

    depth = 4 - game_row
    min_dist = min(game_col - 1, 8 - game_col, game_row - 1)

    if min_dist >= 2:
        ring = 1
    elif min_dist >= 1:
        ring = 2
    else:
        ring = 3

    return f"{sector}{ring}/{opponent}{depth}.{flank}"


def _build_tables() -> tuple[dict[str, str], dict[str, str]]:
    """Строит две lookup-таблицы: server→tri и tri→server."""
    s2t: dict[str, str] = {}
    t2s: dict[str, str] = {}

    for sector in ("W", "B", "R"):
        columns = _COLUMN_ORDER[sector]
        rows = _ROW_ORDER[sector]

        for gc_idx, col_letter in enumerate(columns):
            game_col = gc_idx + 1
            for gr_idx, server_row in enumerate(rows):
                game_row = gr_idx + 1
                server = f"{col_letter}{server_row}"
                tri = _compute_notation(sector, game_col, game_row)
                s2t[server] = tri
                t2s[tri] = server

    return s2t, t2s


# Предвычисленные таблицы (строятся один раз при импорте модуля)
_SERVER_TO_TRI, _TRI_TO_SERVER = _build_tables()


# ═══════════════════════════════════════════════════════════════════
# ПУБЛИЧНЫЙ API
# ═══════════════════════════════════════════════════════════════════


def to_triumvirate(server_notation: str) -> str:
    """A1 → W3/B3.0, D4 → C/W.B. Raises KeyError if not found."""
    key = server_notation.upper().strip()
    if key not in _SERVER_TO_TRI:
        raise KeyError(f"Unknown server notation: '{server_notation}'")
    return _SERVER_TO_TRI[key]


def to_server(tri_notation: str) -> str:
    """W3/B3.0 → A1, C/W.B → D4. Raises KeyError if not found."""
    key = tri_notation.strip()
    if key not in _TRI_TO_SERVER:
        raise KeyError(f"Unknown Triumvirate notation: '{tri_notation}'")
    return _TRI_TO_SERVER[key]


def convert_legal_moves(
    legal: dict[str, list[str]],
) -> dict[str, list[str]]:
    """{"A2": ["A3","A4"]} → {"W3/B2.0": ["W3/B1.0","W3/B0.0"]}"""
    result: dict[str, list[str]] = {}
    for from_sq, targets in legal.items():
        tri_from = to_triumvirate(from_sq)
        result[tri_from] = [to_triumvirate(t) for t in targets]
    return result


def convert_legal_moves_back(
    tri_legal: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Обратная конвертация: Triumvirate legal_moves → серверные."""
    result: dict[str, list[str]] = {}
    for from_sq, targets in tri_legal.items():
        srv_from = to_server(from_sq)
        result[srv_from] = [to_server(t) for t in targets]
    return result


def convert_board(board: list[dict]) -> list[dict]:
    """Добавляет tri_notation к каждой фигуре, не мутируя оригинал."""
    result = []
    for piece in board:
        p = dict(piece)
        notation = p.get("notation", "")
        if notation:
            try:
                p["tri_notation"] = to_triumvirate(notation)
            except KeyError:
                p["tri_notation"] = notation
        result.append(p)
    return result


def parse_triumvirate(tri: str) -> dict:
    """Парсит TRIUMVIRATE нотацию в компоненты.

    'W2/B2.3' → {'sector':'W', 'ring':2, 'opponent':'B',
                  'depth':2, 'flank':3, 'buried':4, 'rosette':False}
    'C/W.B'   → {'sector':'W', 'ring':0, 'opponent':'B',
                  'depth':0, 'flank':0, 'buried':0, 'rosette':True}

    Raises KeyError if notation is invalid.
    """
    tri = tri.strip()
    if tri not in _TRI_TO_SERVER:
        raise KeyError(f"Unknown Triumvirate notation: '{tri}'")

    if tri.startswith("C/"):
        # Rosette: C/W.B or C/B.R etc.
        parts = tri[2:].split(".")
        return {
            "sector": parts[0],
            "ring": 0,
            "opponent": parts[1],
            "depth": 0,
            "flank": 0,
            "buried": 0,
            "rosette": True,
        }

    # Regular: W2/B2.3
    sector = tri[0]
    ring = int(tri[1])
    opponent = tri[3]
    rest = tri[4:].split(".")
    depth = int(rest[0])
    flank = int(rest[1])
    return {
        "sector": sector,
        "ring": ring,
        "opponent": opponent,
        "depth": depth,
        "flank": flank,
        "buried": ring + depth,
        "rosette": False,
    }


def convert_move_back(tri_from: str, tri_to: str) -> tuple[str, str]:
    """Конвертирует ход из Triumvirate обратно в серверную нотацию."""
    return to_server(tri_from), to_server(tri_to)
