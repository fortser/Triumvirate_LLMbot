"""Сборка многослойных промптов из шаблонов и игрового состояния.

Зависимости: settings (через параметр, не через import верхнего уровня).
Зависимые: bot_runner.
"""
from __future__ import annotations

from settings import DEFAULT_RESPONSE_FORMAT, Settings


class PromptBuilder:
    """Assembles multi-layer prompts from settings + game state."""

    def build(self, state: dict, settings: Settings) -> list[dict]:
        legal = state.get("legal_moves", {})
        current = state.get("current_player", "?")
        move_num = state.get("move_number", 0)
        pos3pf = state.get("position_3pf") or "N/A"
        last_raw = state.get("last_move")
        check_info = state.get("check")

        last_text = "none (game start)"
        if last_raw:
            last_text = (
                f"{last_raw.get('from_square','?')} → {last_raw.get('to_square','?')}"
            )
            mt = last_raw.get("move_type", "")
            if mt and mt != "normal":
                last_text += f" ({mt})"

        check_text = ""
        if check_info and check_info.get("is_check"):
            checked = ", ".join(check_info.get("checked_colors", []))
            check_text = f"⚠️ CHECK: {checked} is in check!"

        board_text = self._fmt_board(state.get("board", []), current)
        legal_text = self._fmt_legal(legal)

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

        fmt = settings["response_format"]
        fmt_instruction = DEFAULT_RESPONSE_FORMAT.get(
            fmt, DEFAULT_RESPONSE_FORMAT["json_thinking"]
        )

        sys_parts = [settings["system_prompt"].strip()]
        rules = (settings["additional_rules"] or "").strip()
        if rules:
            sys_parts.append(f"\nADDITIONAL RULES:\n{rules}")
        sys_parts.append(f"\nOUTPUT FORMAT:\n{fmt_instruction}")
        system = "\n".join(p for p in sys_parts if p)

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

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
