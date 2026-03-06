"""Утилиты форматирования и экспорта данных.

Форматирование одного или нескольких ходов в Markdown / JSON
для копирования в буфер обмена.
"""
from __future__ import annotations

import json
from typing import Any


def move_to_markdown(trace: dict) -> str:
    """Форматирует один ход как Markdown-блок для вставки в чат."""
    move_str = f"{trace['move_from']}→{trace['move_to']}"
    if trace.get("promotion"):
        move_str += f" ={trace['promotion']}"

    lines = [
        f"## Move #{trace['move_number']} "
        f"({trace['model']}, game {trace['game_id_short']})",
        "",
        f"**Outcome:** {trace['outcome']}",
        f"**Move:** {move_str}",
        f"**Time:** {trace['llm_time']:.1f}s | "
        f"**Tokens:** {trace['total_tokens']} | "
        f"**Cost:** ${trace['cost_usd']:.6f}",
    ]

    if trace.get("retries", 0) > 0:
        lines.append(f"**Retries:** {trace['retries']}")

    thinking = trace.get("thinking", "")
    if thinking:
        lines.extend(["", "**Thinking:**", f"> {thinking}"])

    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def moves_to_markdown(traces: list[dict]) -> str:
    """Форматирует несколько ходов для мультиселекта."""
    parts = [move_to_markdown(t) for t in traces]
    return "\n\n".join(parts)


def section_to_json(data: Any, indent: int = 2) -> str:
    """Форматирует данные как pretty JSON."""
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def format_prompt_pipeline_md(trace: dict) -> str:
    """Форматирует prompt pipeline для экспорта."""
    lines = [
        f"# Prompt Pipeline — Move #{trace['move_number']} "
        f"({trace['model']}, game {trace['game_id_short']})",
        "",
        "## System Prompt (template)",
        "```",
        trace.get("system_prompt_template", "(empty)"),
        "```",
        "",
        "## User Prompt (template)",
        "```",
        trace.get("user_template", "(empty)"),
        "```",
        "",
        "## Rendered System Prompt",
        "```",
        trace.get("rendered_system", "(empty)"),
        "```",
        "",
        "## Rendered User Prompt",
        "```",
        trace.get("rendered_user", "(empty)"),
        "```",
    ]

    rules = trace.get("additional_rules", "")
    if rules:
        lines.extend(["", "## Additional Rules", "```", rules, "```"])

    fmt = trace.get("response_format_instruction", "")
    if fmt:
        lines.extend(
            ["", "## Response Format Instruction", "```", fmt, "```"]
        )

    return "\n".join(lines)


def format_parser_md(raw_trace: dict) -> str:
    """Форматирует секцию парсера."""
    attempts = raw_trace.get("parser_attempts") or []
    move_sel = raw_trace.get("move_selected") or {}
    lines = ["# Parser Results", ""]

    for att in attempts:
        n = att.get("attempt", "?")
        lines.append(f"## Attempt {n}")
        coords = att.get("coordinates_found", [])
        lines.append(f"**Coordinates found:** {', '.join(coords)}")
        pairs = att.get("pairs_tested", [])
        lines.append(f"**Pairs tested:**")
        for p in pairs:
            lines.append(f"  - {p}")
        lines.append(f"**Valid:** {att.get('valid', '?')}")
        lines.append("")

    if move_sel:
        f = move_sel.get("from", "?")
        t = move_sel.get("to", "?")
        promo = move_sel.get("promotion")
        promo_str = f" ={promo}" if promo else ""
        lines.append(f"**Selected move:** {f}→{t}{promo_str}")

    return "\n".join(lines)


def format_llm_interaction_md(raw_trace: dict) -> str:
    """Форматирует LLM requests/responses."""
    requests = raw_trace.get("llm_requests") or []
    responses = raw_trace.get("llm_responses") or []

    lines = ["# LLM Interaction", ""]

    for req in requests:
        n = req.get("attempt", "?")
        lines.append(f"## Request (attempt {n})")
        for msg in req.get("messages", []):
            role = msg.get("role", "?")
            content = msg.get("content", "")
            lines.append(f"### [{role}]")
            lines.append(f"```")
            lines.append(content)
            lines.append(f"```")
            lines.append("")

    for resp in responses:
        n = resp.get("attempt", "?")
        lines.append(f"## Response (attempt {n})")
        lines.append(f"**Time:** {resp.get('time_sec', 0):.1f}s | "
                      f"**Chars:** {resp.get('response_chars', 0)}")
        usage = resp.get("usage") or {}
        if usage:
            lines.append(
                f"**Tokens:** prompt={usage.get('prompt_tokens', 0)} | "
                f"completion={usage.get('completion_tokens', 0)} | "
                f"reasoning={usage.get('reasoning_tokens', 0)} | "
                f"total={usage.get('total_tokens', 0)}"
            )
        cost = resp.get("cost") or {}
        if cost:
            lines.append(
                f"**Cost:** ${cost.get('total_cost_usd', 0):.6f}"
            )
        lines.append(f"```")
        lines.append(resp.get("raw_response", "(empty)"))
        lines.append(f"```")
        lines.append("")

    return "\n".join(lines)
