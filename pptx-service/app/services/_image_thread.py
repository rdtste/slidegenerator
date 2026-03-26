"""Dedicated event loop thread for image generation.

The PPTX renderer is synchronous and blocks the main event loop.
Running async image generation via asyncio.run() in a ThreadPoolExecutor(1)
creates a new event loop per call — expensive. Instead, we keep a single
background event loop alive in a daemon thread and schedule coroutines on it.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Callable, Coroutine

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    if _loop is not None and _loop.is_running():
        return _loop
    with _lock:
        if _loop is not None and _loop.is_running():
            return _loop
        _loop = asyncio.new_event_loop()
        _thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _thread.start()
    return _loop


def run_image_gen_sync(
    description: str,
    async_fn: Callable[..., Coroutine[None, None, Path | None]],
) -> Path | None:
    """Run an async image generation function from a sync context.

    Uses a shared background event loop thread to avoid creating
    a new event loop + thread per image call.
    """
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(async_fn(description), loop)
    return future.result(timeout=90)
