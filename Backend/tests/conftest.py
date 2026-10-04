from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from control_layer.infrastructure.settings import Settings
from control_layer.presentation.app import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BACKEND_DIR / "config"
OLLAMA_MODEL = "qwen2.5:7b"
ADMIN_HEADERS = {"X-Admin-Token": "admin-dev-token"}
_EMPTY_MCP = "servers: []\n"


def _ollama_available() -> bool:
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=1.5)
        names = [m.get("name") for m in response.json().get("models", [])]
        return OLLAMA_MODEL in names
    except Exception:
        return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    ollama_ok: bool | None = None
    for item in items:
        if item.get_closest_marker("ollama"):
            if ollama_ok is None:
                ollama_ok = _ollama_available()
            if not ollama_ok:
                reason = f"Ollama model {OLLAMA_MODEL} not available"
                item.add_marker(pytest.mark.skip(reason=reason))


@dataclass
class RunningApp:
    app: object
    client: httpx.AsyncClient
    settings: Settings
    policy_path: Path
    workdir: Path


class _LifespanRunner:
    def __init__(self, app: object) -> None:
        self._app = app
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self._error: BaseException | None = None
        self._task: asyncio.Task[None] | None = None

    async def _run(self) -> None:
        try:
            async with self._app.router.lifespan_context(self._app):  # type: ignore[attr-defined]
                self._ready.set()
                await self._stop.wait()
        except BaseException as exc:
            self._error = exc
            self._ready.set()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        await self._ready.wait()
        if self._error is not None:
            raise self._error

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task


def make_settings(
    workdir: Path,
    *,
    policy_text: str | None = None,
    real_mcp: bool = True,
    model_provider: str = "mock",
    gateway_default_user: str | None = "anna.kowalska",
) -> tuple[Settings, Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    policy_path = workdir / "policy.yaml"
    if policy_text is None:
        shutil.copy(CONFIG_DIR / "policy.yaml", policy_path)
    else:
        policy_path.write_text(policy_text, encoding="utf-8")
    if real_mcp:
        mcp_path = CONFIG_DIR / "mcp_servers.yaml"
    else:
        mcp_path = workdir / "mcp_servers.yaml"
        mcp_path.write_text(_EMPTY_MCP, encoding="utf-8")
    settings = Settings(
        model_provider=model_provider,
        gateway_default_user=gateway_default_user,
        redis_url="redis://127.0.0.1:1/0",
        policy_file=str(policy_path),
        mcp_servers_file=str(mcp_path),
        signatures_file=str(CONFIG_DIR / "attack_signatures.yaml"),
        users_file=str(CONFIG_DIR / "users.yaml"),
        alerts_xlsx=str(workdir / "alerts.xlsx"),
        audit_jsonl=str(workdir / "calls.jsonl"),
        ml_tree_path=str(workdir / "prompt_injection_tree.joblib"),
        training_samples_path=str(workdir / "judge_samples.jsonl"),
    )
    return settings, policy_path


@contextlib.asynccontextmanager
async def running_app(
    workdir: Path,
    *,
    policy_text: str | None = None,
    real_mcp: bool = True,
    model_provider: str = "mock",
    gateway_default_user: str | None = "anna.kowalska",
) -> AsyncIterator[RunningApp]:
    settings, policy_path = make_settings(
        workdir,
        policy_text=policy_text,
        real_mcp=real_mcp,
        model_provider=model_provider,
        gateway_default_user=gateway_default_user,
    )
    app = create_app(settings)
    runner = _LifespanRunner(app)
    await runner.start()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as c:
            yield RunningApp(app, c, settings, policy_path, workdir)
    finally:
        await runner.stop()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def shared_app(tmp_path_factory: pytest.TempPathFactory) -> AsyncIterator[RunningApp]:
    async with running_app(tmp_path_factory.mktemp("shared")) as running:
        yield running


@pytest_asyncio.fixture(loop_scope="session")
async def api(shared_app: RunningApp) -> AsyncIterator[httpx.AsyncClient]:
    await shared_app.client.post("/api/demo/reset", headers=ADMIN_HEADERS)
    await shared_app.app.state.container.clear_logs.execute()
    yield shared_app.client


@pytest.fixture
def policy_text() -> str:
    return (CONFIG_DIR / "policy.yaml").read_text(encoding="utf-8")


AppFactory = Callable[..., contextlib.AbstractAsyncContextManager[RunningApp]]


@pytest.fixture
def isolated_app(tmp_path: Path) -> AppFactory:
    def factory(
        policy_text: str | None = None,
        real_mcp: bool = False,
        gateway_default_user: str | None = "anna.kowalska",
    ):
        return running_app(
            tmp_path / "app",
            policy_text=policy_text,
            real_mcp=real_mcp,
            gateway_default_user=gateway_default_user,
        )

    return factory


async def get_token(client: httpx.AsyncClient, sub: str) -> str:
    response = await client.post("/auth/token", json={"sub": sub})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token: str, session: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if session:
        headers["X-Session-Id"] = session
    return headers


async def call_tool(
    client: httpx.AsyncClient,
    token: str,
    server: str,
    tool: str,
    arguments: dict | None = None,
    session: str | None = None,
) -> httpx.Response:
    return await client.post(
        "/v1/tools/call",
        json={"server": server, "tool": tool, "arguments": arguments or {}, "session_id": session},
        headers=bearer(token),
    )


async def chat(
    client: httpx.AsyncClient,
    token: str,
    message: str,
    model: str = "mock",
    **extra: object,
) -> httpx.Response:
    body = {"model": model, "messages": [{"role": "user", "content": message}], **extra}
    return await client.post("/v1/chat/completions", json=body, headers=bearer(token))


async def read_sse(
    app: object,
    path: str,
    *,
    until: Callable[[list[tuple[str, dict]]], bool],
    trigger: Callable[[], Awaitable[None]] | None = None,
    timeout_s: float = 20.0,
) -> list[tuple[str, dict]]:
    queue: asyncio.Queue[dict] = asyncio.Queue()
    disconnect = asyncio.Event()
    request_sent = False

    async def receive() -> dict:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        await queue.put(message)

    path_only, _, query = path.partition("?")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path_only,
        "raw_path": path_only.encode(),
        "query_string": query.encode(),
        "headers": [(b"host", b"test"), (b"accept", b"text/event-stream")],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
        "root_path": "",
    }
    task = asyncio.create_task(app(scope, receive, send))  # type: ignore[operator]
    events: list[tuple[str, dict]] = []
    buffer = ""
    try:
        if trigger is not None:
            await asyncio.sleep(0.3)
            await trigger()
        async with asyncio.timeout(timeout_s):
            while not until(events):
                message = await queue.get()
                if message["type"] != "http.response.body":
                    continue
                buffer += message.get("body", b"").decode("utf-8").replace("\r\n", "\n")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    name, data = "message", ""
                    for line in block.split("\n"):
                        if line.startswith("event:"):
                            name = line[6:].strip()
                        elif line.startswith("data:"):
                            data += line[5:].strip()
                    if data:
                        events.append((name, json.loads(data)))
    finally:
        disconnect.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    return events
