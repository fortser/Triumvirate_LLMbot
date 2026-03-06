#!/usr/bin/env python3
"""Triumvirate LLM Bot — GUI v2.2

Graphical LLM-bot for Three-Player Chess Arena (triumvirate4llm.com).

Requirements:
    pip install nicegui httpx websockets

Usage:
    python main.py              # desktop window
    python main.py --web        # web server (http://localhost:8090)
    python main.py --web --port 9000
"""
from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from gui import create_gui
from settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Triumvirate LLM Bot GUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py              # desktop window\n"
            "  python main.py --web        # http://localhost:8090\n"
            "  python main.py --web --port 9000\n"
        ),
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run as web server instead of desktop window",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host (web mode)")
    parser.add_argument(
        "--port", type=int, default=8090, help="Port (web mode)"
    )
    parser.add_argument(
        "--settings",
        default=None,
        help="Path to settings JSON file (default: llm_bot_gui_settings_v2.json). "
        "Use different files to run multiple instances simultaneously.",
    )
    args = parser.parse_args()

    if args.settings:
        Settings._file = Path(args.settings)

    settings = Settings()
    instance_label = (
        f" [{Settings._file.stem}]" if args.settings else ""
    )
    create_gui(settings)

    if args.web:
        ui.run(
            host=args.host,
            port=args.port,
            title=f"Triumvirate LLM Bot{instance_label}",
            reload=False,
            show=False,
        )
    else:
        ui.run(
            title=f"Triumvirate LLM Bot{instance_label}",
            native=True,
            window_size=(1440, 900),
            reload=False,
        )


if __name__ == "__main__":
    main()
