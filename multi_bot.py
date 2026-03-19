"""Multi-bot headless orchestrator.

Запускает N ботов параллельно, каждый с уникальной LLM-моделью из пула.
Каждый бот играет свою отдельную игру (auto_skip_waiting=True).

Зависимости: bot_runner, settings, constants.
"""
from __future__ import annotations

import asyncio
import json
import random
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from constants import make_bot_name
from settings import Settings


# ─── SettingsOverride ────────────────────────────────────────────────────────

class SettingsOverride:
    """Proxy over Settings that overrides specific keys.

    Virtual keys (system_prompt, user_template, api_key) are delegated
    to the base Settings. save() is a no-op — these are ephemeral.
    """

    def __init__(self, base: Settings, overrides: dict[str, Any]) -> None:
        self._base = base
        self._overrides = overrides

    def __getitem__(self, key: str) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        return self._base[key]

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        return self._base.get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        self._overrides[key] = value

    def save(self) -> None:
        pass  # ephemeral — never persist


# ─── BotResult ───────────────────────────────────────────────────────────────

@dataclass
class BotResult:
    index: int
    model: str
    color: str = ""
    moves: int = 0
    game_result: str = "error"  # win / loss / draw / error
    cost: float = 0.0
    duration: float = 0.0
    error: str = ""


# ─── BotLogger ───────────────────────────────────────────────────────────────

class BotLogger:
    """Per-bot logger: full log to file, short lines to console."""

    def __init__(
        self,
        index: int,
        model: str,
        log_dir: Path,
        console_lock: asyncio.Lock,
    ) -> None:
        self.index = index
        self.model_short = model.split("/")[-1] if "/" in model else model
        self._console_lock = console_lock

        safe_name = self.model_short.replace("/", "_").replace("\\", "_")
        self._log_file = log_dir / f"bot_{index}_{safe_name}.log"
        self._log_file.touch()

    def _ts(self) -> str:
        return time.strftime("%H:%M:%S")

    def log(self, msg: str) -> None:
        ts = self._ts()
        line = f"[{ts}] [Bot#{self.index} {self.model_short}] {msg}"
        # Write to file (sync — small writes)
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def console(self, msg: str) -> None:
        ts = self._ts()
        line = f"[{ts}] [Bot#{self.index} {self.model_short}] {msg}"
        async with self._console_lock:
            print(line, flush=True)


# ─── Model selection ─────────────────────────────────────────────────────────

@dataclass
class PoolConfig:
    models: list[str]
    start_delay: float = 0.0  # seconds between bot launches


def load_models_pool(path: Path) -> PoolConfig:
    """Load model names and session config from a JSON pool file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    models = data.get("models", [])
    if not models:
        raise ValueError(f"No models found in {path}")
    start_delay = float(data.get("start_delay", 0))
    return PoolConfig(models=models, start_delay=start_delay)


def _select_models(
    pool: list[str], count: int, explicit: list[str] | None
) -> list[str]:
    """Select models: explicit list takes priority, otherwise sample from pool."""
    if explicit:
        return list(explicit)
    if count <= len(pool):
        return random.sample(pool, count)
    return random.choices(pool, k=count)


# ─── Single bot task ─────────────────────────────────────────────────────────

async def _run_single_bot(
    index: int,
    settings: Settings,
    model: str,
    logger: BotLogger,
) -> BotResult:
    """Run one bot instance, return its result."""
    from bot_runner import BotRunner

    result = BotResult(index=index, model=model)
    start_time = time.monotonic()

    # Force bot_name regeneration from the override model
    # so the game server sees the correct model in statistics.
    # Without this, bot_name from base config (with the default model) is sent.
    provider = settings.get("provider", "")
    bot_name = make_bot_name(provider, model)

    overrides: dict[str, Any] = {
        "model": model,
        "bot_name": bot_name,
        "auto_skip_waiting": True,
    }
    bot_settings = SettingsOverride(settings, overrides)

    color = ""
    game_result_str = "error"

    def on_log(msg: str) -> None:
        logger.log(msg)

    def on_status(msg: str) -> None:
        logger.log(f"[STATUS] {msg}")

    def on_state(state: dict) -> None:
        pass

    runner = BotRunner(bot_settings, on_log, on_status, on_state)

    try:
        await logger.console(f"starting with model {model}")
        runner.start()

        # Wait for the bot to finish
        while runner._running:
            await asyncio.sleep(1)

        # Wait for the task to complete
        if runner._task and not runner._task.done():
            try:
                await asyncio.wait_for(runner._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        color = runner.arena.color or ""
        moves = runner.stats["moves"]
        cost = runner.stats["total_cost_usd"]

        result.color = color.upper()
        result.moves = moves
        result.cost = cost

        # Try to determine game result from the last status message
        # BotRunner logs winner info — we can't easily get it from here,
        # so mark as "finished" if moves > 0
        result.game_result = "finished" if moves > 0 else "no_moves"

        await logger.console(
            f"finished: color={result.color} moves={moves} cost=${cost:.4f}"
        )

    except asyncio.CancelledError:
        runner.stop()
        if runner._task and not runner._task.done():
            try:
                await asyncio.wait_for(runner._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        result.game_result = "cancelled"
        await logger.console("cancelled")

    except Exception as e:
        runner.stop()
        result.error = str(e)
        result.game_result = "error"
        await logger.console(f"error: {e}")

    finally:
        result.duration = time.monotonic() - start_time

    return result


# ─── Summary ─────────────────────────────────────────────────────────────────

def print_summary(results: list[BotResult]) -> None:
    """Print a summary table of all bot results."""
    print()
    print("=" * 85)
    print(
        f"{'#':>2} | {'Model':<30} | {'Color':<5} | {'Moves':>5} | "
        f"{'Result':<10} | {'Cost':>9} | {'Duration':>8}"
    )
    print("-" * 85)
    for r in results:
        model_display = r.model[:30]
        dur_m, dur_s = divmod(int(r.duration), 60)
        dur_str = f"{dur_m}m {dur_s:02d}s"
        cost_str = f"${r.cost:.4f}"
        print(
            f"{r.index:>2} | {model_display:<30} | {r.color:<5} | "
            f"{r.moves:>5} | {r.game_result:<10} | {cost_str:>9} | {dur_str:>8}"
        )
    print("=" * 85)
    total_cost = sum(r.cost for r in results)
    total_moves = sum(r.moves for r in results)
    print(f"Total: {len(results)} bots, {total_moves} moves, ${total_cost:.4f}")
    print()


# ─── Main orchestrator ───────────────────────────────────────────────────────

async def _run_all(
    settings: Settings,
    models: list[str],
    start_delay: float = 0.0,
) -> list[BotResult]:
    """Run all bots concurrently and collect results."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = Path(__file__).parent / "logs" / f"multi_{timestamp}"
    log_dir.mkdir(parents=True, exist_ok=True)

    console_lock = asyncio.Lock()
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Starting {len(models)} bots...", flush=True)
    for i, m in enumerate(models):
        print(f"  Bot#{i}: {m}", flush=True)
    if start_delay > 0:
        print(f"  Start delay: {start_delay}s between bots", flush=True)
    print(f"  Logs: {log_dir}", flush=True)
    print()

    tasks: list[asyncio.Task] = []
    for i, model in enumerate(models):
        logger = BotLogger(i, model, log_dir, console_lock)
        if i > 0 and start_delay > 0:
            await asyncio.sleep(start_delay)
        task = asyncio.create_task(
            _run_single_bot(i, settings, model, logger),
            name=f"bot_{i}",
        )
        tasks.append(task)

    stop_event = asyncio.Event()

    def _handle_cancel() -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"\n[{ts}] Ctrl+C — stopping all bots...", flush=True)
        for t in tasks:
            t.cancel()
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_cancel)

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except (KeyboardInterrupt, asyncio.CancelledError):
        _handle_cancel()
        # Wait for tasks to finish after cancellation
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to BotResult
    final: list[BotResult] = []
    for i, r in enumerate(results):
        if isinstance(r, BotResult):
            final.append(r)
        elif isinstance(r, Exception):
            final.append(BotResult(
                index=i,
                model=models[i],
                game_result="error",
                error=str(r),
            ))
        else:
            final.append(BotResult(index=i, model=models[i], game_result="error"))

    return final


def run_multi_bot(
    settings: Settings,
    models: list[str],
    start_delay: float = 0.0,
) -> None:
    """Entry point: run multiple bots and print summary."""
    try:
        results = asyncio.run(_run_all(settings, models, start_delay))
    except KeyboardInterrupt:
        print("\nAborted.", flush=True)
        return

    print_summary(results)
