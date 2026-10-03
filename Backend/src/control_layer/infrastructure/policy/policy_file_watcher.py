from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class PolicyFileWatcher:
    def __init__(
        self,
        path: Path | str,
        reload: Callable[[], Awaitable[object]],
        interval_s: float = 1.0,
    ) -> None:
        self._path = Path(path)
        self._reload = reload
        self._interval_s = interval_s
        self._last_mtime: float | None = None
        self._task: asyncio.Task[None] | None = None

    async def check_once(self) -> None:
        try:
            if not self._path.exists():
                return
            mtime = self._path.stat().st_mtime
            if self._last_mtime is None:
                self._last_mtime = mtime
                return
            if mtime == self._last_mtime:
                return
            self._last_mtime = mtime
            await self._reload()
        except Exception as exc:
            logger.error("Policy file watcher failed: %s", exc, exc_info=True)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval_s)
            await self.check_once()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
