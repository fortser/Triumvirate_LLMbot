#!/usr/bin/env python3
"""Triumvirate LLM Bot — GUI v2.2

Graphical LLM-bot for Three-Player Chess Arena (triumvirate4llm.com).

Requirements:
    pip install nicegui httpx websockets

Usage:
    python main.py              # desktop window
    python main.py --web        # web server (http://localhost:8090)
    python main.py --web --port 9000
    python main.py --headless   # without GUI, settings from JSON
"""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import time
from pathlib import Path

from settings import Settings


def _run_headless(settings: Settings) -> None:
    """Run bot without GUI — console-only mode."""
    from bot_runner import BotRunner

    label = Settings._file.stem

    def _log(msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)

    def _status(msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] [STATUS] {msg}", flush=True)

    def _on_state(_state: dict) -> None:
        pass  # state updates не нужны в консоли — всё есть в логах

    async def _run() -> None:
        runner = BotRunner(settings, _log, _status, _on_state)

        stop_event = asyncio.Event()

        def _handle_signal() -> None:
            _log(f"⛔ Получен сигнал завершения, останавливаю бот [{label}]...")
            runner.stop()
            stop_event.set()

        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, _handle_signal)
        else:
            # Windows: signal handlers через loop не работают,
            # KeyboardInterrupt перехватывается ниже
            pass

        _log(f"▶️ Запуск бота [{label}] в headless-режиме")
        runner.start()

        try:
            # Ждём завершения задачи бота или сигнала остановки
            while runner._running and not stop_event.is_set():
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            _handle_signal()

        # Даём боту время корректно завершиться
        if runner._task and not runner._task.done():
            try:
                await asyncio.wait_for(runner._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        _log(f"🏁 Бот [{label}] завершён")

    asyncio.run(_run())


def _run_gui(settings: Settings, args: argparse.Namespace) -> None:
    """Run bot with NiceGUI interface."""
    from nicegui import ui

    from gui import create_gui

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Triumvirate LLM Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                          # desktop window\n"
            "  python main.py --web                    # http://localhost:8090\n"
            "  python main.py --web --port 9000\n"
            "  python main.py --headless               # без GUI\n"
            "  python main.py --headless --settings bot2.json\n"
        ),
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run as web server instead of desktop window",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without GUI (console only). "
        "All settings are read from the JSON config file.",
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
    parser.add_argument(
        "--bots",
        type=int,
        default=1,
        help="Number of bots to run in parallel (headless multi-bot mode).",
    )
    parser.add_argument(
        "--models-pool",
        default="models_pool.json",
        help="Path to models pool JSON file (default: models_pool.json).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Explicit list of models to use (overrides --models-pool).",
    )
    parser.add_argument(
        "--start-delay",
        type=float,
        default=None,
        help="Delay in seconds between bot launches (overrides models_pool.json).",
    )
    args = parser.parse_args()

    if args.headless and args.web:
        print("Error: --headless и --web нельзя использовать одновременно.",
              file=sys.stderr)
        sys.exit(1)

    if args.settings:
        Settings._file = Path(args.settings)

    settings = Settings()

    if args.headless:
        use_multi = args.bots > 1 or args.models
        if use_multi:
            from multi_bot import _select_models, load_models_pool, run_multi_bot

            start_delay = 0.0
            if args.models:
                models = list(args.models)
                # Load start_delay from pool file if it exists
                pool_path = Path(args.models_pool)
                if not pool_path.is_absolute():
                    pool_path = Path(__file__).parent / pool_path
                if pool_path.exists():
                    pool_cfg = load_models_pool(pool_path)
                    start_delay = pool_cfg.start_delay
            else:
                pool_path = Path(args.models_pool)
                if not pool_path.is_absolute():
                    pool_path = Path(__file__).parent / pool_path
                pool_cfg = load_models_pool(pool_path)
                models = _select_models(pool_cfg.models, args.bots, None)
                start_delay = pool_cfg.start_delay

            # CLI --start-delay overrides pool config
            if args.start_delay is not None:
                start_delay = args.start_delay

            run_multi_bot(settings, models, start_delay)
        else:
            _run_headless(settings)
    else:
        _run_gui(settings, args)


if __name__ == "__main__":
    main()
