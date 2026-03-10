"""Сборка многослойных промптов из шаблонов и игрового состояния.

Зависимости: settings (через параметр, не через import верхнего уровня).
Зависимые: bot_runner.
"""
from __future__ import annotations

from settings import Settings, get_response_format


class PromptBuilder:
    """Assembles multi-layer prompts from settings + game state."""

    def build(
        self,
        state: dict,
        settings: Settings,
        *,
        tri_legal: dict | None = None,
        tri_board: list[dict] | None = None,
        tri_last_move: tuple[str, str] | None = None,
    ) -> list[dict]:
        """Build prompt messages.

        Args:
            state: raw server state dict.
            settings: application settings.
            tri_legal: legal moves in Triumvirate notation (if enabled).
            tri_board: board pieces with tri_notation field (if enabled).
            tri_last_move: (tri_from, tri_to) of last move (if enabled).
        """
        use_tri = tri_legal is not None
        legal = tri_legal if use_tri else state.get("legal_moves", {})
        current = state.get("current_player", "?")
        move_num = state.get("move_number", 0)
        pos3pf = state.get("position_3pf") or "N/A"
        last_raw = state.get("last_move")
        check_info = state.get("check")

        # ── Last move text ────────────────────────────────────────────
        last_text = "none (game start)"
        if last_raw:
            if use_tri and tri_last_move:
                lf, lt = tri_last_move
                last_text = f"{lf} → {lt}"
            else:
                last_text = (
                    f"{last_raw.get('from_square', '?')} → "
                    f"{last_raw.get('to_square', '?')}"
                )
            mt = last_raw.get("move_type", "")
            if mt and mt != "normal":
                last_text += f" ({mt})"

        check_text = ""
        if check_info and check_info.get("is_check"):
            checked = ", ".join(check_info.get("checked_colors", []))
            check_text = f"⚠️ CHECK: {checked} is in check!"

        # Fallback: server may return check=null but players[].status="in_check"
        if not check_text:
            for p in state.get("players", []):
                if p.get("color") == current and p.get("status") == "in_check":
                    check_text = (
                        "⚠️ YOU ARE IN CHECK! You MUST move your Leader to safety "
                        "or block the attack. Any other move is illegal."
                    )
                    break

        # ── Board & legal text ────────────────────────────────────────
        if use_tri and tri_board is not None:
            board_text = self._fmt_board_tri(tri_board, current)
        else:
            board_text = self._fmt_board(state.get("board", []), current)

        legal_text = self._fmt_legal(legal)

        # ── Template substitution ─────────────────────────────────────
        tmpl = settings["user_template"]
        subs = {
            "move_number": str(move_num),
            "current_player": current.upper(),
            "position_3pf": pos3pf,
            "legal_moves": legal_text,
            "last_move": last_text,
            "board": board_text,
            "check": check_text,
            "color": current.upper(),
        }
        user = self._fill_template(tmpl, subs)

        raw_tmpl = tmpl
        if board_text and "board" not in raw_tmpl:
            user += f"\n\nBoard:\n{board_text}"
        if check_text and "check" not in raw_tmpl:
            user += f"\n\n{check_text}"

        # ── Response format from file (no more _adapt_format_for_tri) ─
        fmt = settings["response_format"]
        fmt_instruction = get_response_format(fmt)

        # ── System prompt ─────────────────────────────────────────────
        sys_parts = [settings["system_prompt"].strip()]
        rules = (settings["additional_rules"] or "").strip()
        if rules:
            sys_parts.append(f"\nADDITIONAL RULES:\n{rules}")
        sys_parts.append(f"\n### OUTPUT FORMAT\n{fmt_instruction}")
        system = "\n".join(p for p in sys_parts if p)

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ── Template helpers ──────────────────────────────────────────────────

    def _fill_template(self, template: str, subs: dict) -> str:
        result = template
        for key, value in subs.items():
            result = result.replace(f"{{{{{key}}}}}", value)
            result = result.replace(f"{{{key}}}", value)
        return result

    def _fmt_legal(self, legal: dict) -> str:
        if not legal:
            return "(none)"
        return "\n".join(
            f"  {src}: {', '.join(sorted(dsts))}"
            for src, dsts in sorted(legal.items())
        )

    # ── Board formatters ──────────────────────────────────────────────────

    def _fmt_board(self, board: list[dict], my_color: str) -> str:
        if not board:
            return ""
        by_color: dict[str, list[str]] = {}
        for p in board:
            c = p.get("color", "?")
            t = p.get("type", "?")
            n = p.get("notation", "?")
            owner = p.get("owner", c)
            label = f"{t[0]}{n}" if t else n
            if owner != c:
                label += f"({owner[0]})"
            by_color.setdefault(c, []).append(label)
        lines = []
        for c, pieces in sorted(by_color.items()):
            tag = " ← YOU" if c == my_color else ""
            lines.append(f"  {c.upper()}{tag}: {' '.join(sorted(pieces))}")
        return "\n".join(lines)

    def _fmt_board_tri(self, tri_board: list[dict], my_color: str) -> str:
        """Format board using Triumvirate notation and piece symbols."""
        if not tri_board:
            return ""

        _PIECE_SYMBOL = {
            "KING": "L", "QUEEN": "M", "ROOK": "T",
            "BISHOP": "D", "KNIGHT": "N", "PAWN": "P",
            # Single-letter codes (current server format)
            "K": "L", "Q": "M", "R": "T", "B": "D",
        }

        by_color: dict[str, list[str]] = {}
        for p in tri_board:
            c = p.get("color", "?")
            t = p.get("type", "?")
            tri_n = p.get("tri_notation") or p.get("notation", "?")
            owner = p.get("owner", c)
            sym = _PIECE_SYMBOL.get(t.upper(), t[0] if t else "?")
            label = f"{sym}:{tri_n}"
            if owner != c:
                label += f"({owner[0]})"
            by_color.setdefault(c, []).append(label)
        lines = []
        for c, pieces in sorted(by_color.items()):
            tag = " ← YOU" if c == my_color else ""
            lines.append(f"  {c.upper()}{tag}: {' '.join(sorted(pieces))}")
        return "\n".join(lines)
