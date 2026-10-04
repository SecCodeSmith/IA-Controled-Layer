from __future__ import annotations

from control_layer.application.dlp.session_vault import SessionVault
from control_layer.application.use_cases.handle_tool_call import HandleToolCallUseCase
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import CallStatus, RuleAction
from control_layer.domain.models.tool import ToolCallRequest, ToolCallResult, ToolDescriptor
from control_layer.domain.policy.parser import parse_policy_document
from tests.unit.application.evaluators.conftest import FakeCacheRepository
from tests.unit.application.use_cases.test_handle_tool_call import (
    _FakeApprovalService,
    _FakeAuditService,
    _FakeCallIds,
    _FakeCircuitBreaker,
    _FakeMcpGateway,
    _FakeModelProvider,
    _FakeRiskService,
    _FakeSessionService,
    _identity,
    _ScriptedPipeline,
)
from tests.unit.domain.policy.test_parser import _minimal_document

EMAIL = "k.wrona@example.com"


class _Catalog:
    async def provisioned_for(self, identity):  # noqa: ANN001, ANN201
        return []

    async def descriptor(self, server: str, tool: str) -> ToolDescriptor:
        return ToolDescriptor(
            server=server,
            name=tool,
            qualified_name=f"{server}.{tool}",
            description="",
            tags=[],
            scope="write",
        )


class _Identities:
    def __init__(self, sub: str = "anna.kowalska") -> None:
        self._sub = sub

    async def resolve(self, token, session_id):  # noqa: ANN001, ANN201
        if token == "bad":
            raise IdentityRejectedError("bad token")
        return _identity().model_copy(update={"sub": self._sub if token != "other" else "intruder"})


class _Policies:
    def __init__(self) -> None:
        rule = {
            "id": "pii_masking",
            "detect": ["email", "pesel"],
            "action": "mask",
            "vault": {"restore": {"email": ["mail.send"]}},
        }
        self._document = parse_policy_document(_minimal_document(rules=[rule]), "h")

    async def current(self):  # noqa: ANN201
        return self._document


def _allowed() -> Decision:
    return Decision(status=CallStatus.ALLOWED, action=RuleAction.allow)


async def _build(steps, vault: SessionVault, gateway: _FakeMcpGateway):  # noqa: ANN001, ANN202
    pipeline = _ScriptedPipeline(steps, _identity())
    return (
        HandleToolCallUseCase(
            pipeline=pipeline,
            tool_catalog=_Catalog(),
            mcp_gateway=gateway,
            approval_service=_FakeApprovalService(),
            session_service=_FakeSessionService(),
            audit_service=_FakeAuditService(),
            circuit_breaker=_FakeCircuitBreaker(),
            risk_service=_FakeRiskService(),
            call_ids=_FakeCallIds(),
            policy_repository=_Policies(),
            model_provider=_FakeModelProvider(),
            vault=vault,
            identity_service=_Identities(),
        ),
        pipeline,
    )


def _mail(to: str, body: str = "hi") -> ToolCallRequest:
    return ToolCallRequest(
        server="mail", tool="send", arguments={"to": to, "nested": {"cc": [to]}, "body": body}
    )


async def test_placeholders_are_restored_for_allowed_tool_and_audit_keeps_placeholders() -> None:
    vault = SessionVault(FakeCacheRepository())
    placeholder = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="anna.kowalska")
    gateway = _FakeMcpGateway(ToolCallResult(content_text="sent"))
    use_case, pipeline = await _build([(_allowed(), None), (_allowed(), None)], vault, gateway)

    outcome = await use_case.execute("token", "s1", _mail(placeholder))

    assert outcome.items_restored == 2
    assert gateway.calls[0].arguments["to"] == EMAIL
    assert gateway.calls[0].arguments["nested"] == {"cc": [EMAIL]}
    assert EMAIL in pipeline.contexts[0].text
    record = use_case._audit_service.records[0][0]
    assert record.items_restored == 2
    assert record.request.payload["to"] == placeholder


async def test_kind_not_allowed_for_the_tool_stays_literal() -> None:
    vault = SessionVault(FakeCacheRepository())
    await vault.placeholder_for("s1", "email", EMAIL, 60, sub="anna.kowalska")
    gateway = _FakeMcpGateway(ToolCallResult(content_text="ok"))
    use_case, _ = await _build([(_allowed(), None), (_allowed(), None)], vault, gateway)

    request = ToolCallRequest(server="calendar", tool="invite", arguments={"to": "[EMAIL_1]"})
    outcome = await use_case.execute("token", "s1", request)

    assert outcome.items_restored == 0
    assert gateway.calls[0].arguments["to"] == "[EMAIL_1]"


async def test_other_session_placeholder_is_not_restored() -> None:
    vault = SessionVault(FakeCacheRepository())
    await vault.placeholder_for("s1", "email", EMAIL, 60, sub="anna.kowalska")
    gateway = _FakeMcpGateway(ToolCallResult(content_text="ok"))
    use_case, _ = await _build([(_allowed(), None), (_allowed(), None)], vault, gateway)

    outcome = await use_case.execute("token", "other", _mail("[EMAIL_1]"))

    assert outcome.items_restored == 0
    assert gateway.calls[0].arguments["to"] == "[EMAIL_1]"


async def test_approved_execution_restores_placeholders_held_in_the_approval() -> None:
    vault = SessionVault(FakeCacheRepository())
    placeholder = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="anna.kowalska")
    gateway = _FakeMcpGateway(ToolCallResult(content_text="sent"))
    use_case, _ = await _build([(_allowed(), None), (_allowed(), None)], vault, gateway)

    outcome = await use_case.execute("token", "s1", _mail(placeholder), approved=True)

    assert outcome.items_restored == 2
    assert gateway.calls[0].arguments["to"] == EMAIL


async def test_same_session_id_with_a_different_caller_is_not_restored() -> None:
    vault = SessionVault(FakeCacheRepository())
    placeholder = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="anna.kowalska")
    gateway = _FakeMcpGateway(ToolCallResult(content_text="ok"))
    use_case, _ = await _build([(_allowed(), None), (_allowed(), None)], vault, gateway)

    outcome = await use_case.execute("other", "s1", _mail(placeholder))

    assert outcome.items_restored == 0
    assert gateway.calls[0].arguments["to"] == placeholder


async def test_unverifiable_token_skips_restoration() -> None:
    vault = SessionVault(FakeCacheRepository())
    placeholder = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="anna.kowalska")
    gateway = _FakeMcpGateway(ToolCallResult(content_text="ok"))
    use_case, _ = await _build([(_allowed(), None), (_allowed(), None)], vault, gateway)

    outcome = await use_case.execute("bad", "s1", _mail(placeholder))

    assert outcome.items_restored == 0
