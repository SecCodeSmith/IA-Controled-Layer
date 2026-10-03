from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import pytest

from control_layer.infrastructure.policy.policy_file_watcher import PolicyFileWatcher


async def test_first_check_establishes_baseline_without_reload(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    calls = []

    async def reload() -> None:
        calls.append(1)

    watcher = PolicyFileWatcher(path, reload)
    await watcher.check_once()

    assert calls == []


async def test_mtime_change_triggers_reload(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    calls = []

    async def reload() -> None:
        calls.append(1)

    watcher = PolicyFileWatcher(path, reload)
    await watcher.check_once()

    future_time = time.time() + 5
    path.write_text("version: 2\n", encoding="utf-8")
    import os

    os.utime(path, (future_time, future_time))

    await watcher.check_once()

    assert calls == [1]


async def test_no_change_does_not_trigger_reload(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    calls = []

    async def reload() -> None:
        calls.append(1)

    watcher = PolicyFileWatcher(path, reload)
    await watcher.check_once()
    await watcher.check_once()
    await watcher.check_once()

    assert calls == []


async def test_missing_file_does_not_raise(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"
    watcher = PolicyFileWatcher(path, lambda: None)

    await watcher.check_once()


async def test_reload_error_is_swallowed_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("version: 1\n", encoding="utf-8")

    async def failing_reload() -> None:
        raise RuntimeError("bad yaml")

    watcher = PolicyFileWatcher(path, failing_reload)
    await watcher.check_once()

    future_time = time.time() + 5
    path.write_text("version: 2\n", encoding="utf-8")
    import os

    os.utime(path, (future_time, future_time))

    with caplog.at_level(logging.ERROR):
        await watcher.check_once()

    assert any("bad yaml" in record.message for record in caplog.records)


async def test_start_stop_runs_polling_loop(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    calls = []

    async def reload() -> None:
        calls.append(1)

    watcher = PolicyFileWatcher(path, reload, interval_s=0.02)
    watcher.start()
    await asyncio.sleep(0.05)

    future_time = time.time() + 5
    path.write_text("version: 2\n", encoding="utf-8")
    import os

    os.utime(path, (future_time, future_time))

    await asyncio.sleep(0.08)
    await watcher.stop()

    assert calls == [1]
