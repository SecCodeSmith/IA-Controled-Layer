from __future__ import annotations

from datetime import UTC, datetime

from control_layer.domain.models.chat import (
    ChatCompletionChoice as Choice,
)
from control_layer.domain.models.chat import (
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.enums import InterceptionPoint, Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.rule import Rule
from control_layer.domain.models.tool import ToolCallRequest, ToolDescriptor
from control_layer.domain.policy.parser import parse_policy_document


def make_identity(
    sub: str = "anna",
    role: Role = Role.developer,
    region: str = "PL",
    location: str = "Krakow",
) -> Identity:
    return Identity(
        sub=sub,
        name="Anna Kowalska",
        role=role,
        location=location,
        region=region,
        agent_id="agent-1",
    )


def make_descriptor(
    server: str = "github",
    name: str = "get_readme",
    tags: list[str] | None = None,
    data_region: str | None = None,
) -> ToolDescriptor:
    return ToolDescriptor(
        server=server,
        name=name,
        qualified_name=f"{server}.{name}",
        description="",
        tags=tags or [],
        data_region=data_region,
        scope="read",
    )


def make_tool_call(
    server: str = "github",
    tool: str = "get_readme",
    arguments: dict | None = None,
    session_id: str = "session-1",
) -> ToolCallRequest:
    return ToolCallRequest(
        server=server, tool=tool, arguments=arguments or {}, session_id=session_id
    )


def make_rule(
    rule_id: str = "rule-1",
    rule_type: str = "rbac",
    action: str = "block",
    match: dict | None = None,
    detect: list[str] | None = None,
    params: dict | None = None,
    on: list[InterceptionPoint] | None = None,
) -> Rule:
    return Rule(
        id=rule_id,
        type=rule_type,
        stage="authorization",
        on=on or InterceptionPoint.all(),
        match=match,
        detect=detect,
        action=action,
        params=params or {},
    )


def make_policy(
    version: int = 1,
    profile: str = "balanced",
    roles: dict | None = None,
    locations: dict | None = None,
    models: dict | None = None,
) -> PolicyDocument:
    data = {
        "version": version,
        "profile": profile,
        "models": models if models is not None else {"allowed": ["mock"], "pricing": {}},
        "roles": (
            roles
            if roles is not None
            else {
                "developer": {"mcp_servers": ["github", "ci"]},
                "hr": {"mcp_servers": ["hr-db", "calendar"]},
                "finance": {
                    "mcp_servers": ["payments"],
                    "transaction_limit": 5000,
                    "beneficiary_allowlist": [],
                },
            }
        ),
        "locations": (
            locations
            if locations is not None
            else {"eu_customers": {"allowed_regions": ["PL", "DE", "FR"]}}
        ),
        "rules": [],
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash=f"hash-{version}")


def make_context(
    identity: Identity | None = None,
    point: InterceptionPoint = InterceptionPoint.prompt,
    text: str = "hello",
    tool_call: ToolCallRequest | None = None,
    metadata: dict | None = None,
    session_id: str = "session-1",
    call_id: str = "call-1",
    no_identity: bool = False,
) -> ProcessingContext:
    default_identity = identity if identity is not None else make_identity()
    resolved_identity = None if no_identity else default_identity
    return ProcessingContext(
        identity=resolved_identity,
        point=point,
        text=text,
        tool_call=tool_call,
        session_id=session_id,
        call_id=call_id,
        metadata=metadata or {},
    )


class FakeCacheRepository:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self.store[key] = value
        self.ttls[key] = ttl

    async def incr(self, key: str, ttl: int | None = None) -> int:
        current = int(self.store.get(key, "0")) + 1
        self.store[key] = str(current)
        self.ttls[key] = ttl
        return current

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def keys(self, prefix: str) -> list[str]:
        return [k for k in self.store if k.startswith(prefix)]

    async def flush(self, prefix: str) -> None:
        for key in list(self.store):
            if key.startswith(prefix):
                del self.store[key]


class FakeSignatureFeed:
    def __init__(self, signatures: list) -> None:
        self._signatures = signatures

    async def signatures(self) -> list:
        return self._signatures

    async def reload(self) -> None:
        return None


class FakePromptClassifier:
    def __init__(self, probability: float) -> None:
        self._probability = probability

    def predict_proba(self, text: str) -> float:
        return self._probability


class FakeModelProvider:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self._content = content
        self._error = error

    async def complete(self, request) -> ChatCompletionResponse:
        if self._error is not None:
            raise self._error
        return ChatCompletionResponse(
            id="resp-1",
            created=0,
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatMessage(role="assistant", content=self._content),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="fake", model="fake-model")


class HangingModelProvider:
    def __init__(self, delay_s: float) -> None:
        self._delay_s = delay_s

    async def complete(self, request) -> ChatCompletionResponse:
        import asyncio

        await asyncio.sleep(self._delay_s)
        raise AssertionError("should have timed out before completing")

    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="fake", model="fake-model")


UTC_NOW = datetime.now(UTC)
