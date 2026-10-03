from __future__ import annotations

from control_layer.application.policy.overridden_policy_repository import (
    OverriddenPolicyRepository,
)
from control_layer.application.services.protection_service import ProtectionService
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.policy.parser import parse_policy_document
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository


def _policy() -> PolicyDocument:
    data = {
        "version": 3,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {"developer": {"mcp_servers": ["github"]}},
        "locations": {},
        "rules": [
            {"id": "pii_masking", "stage": "dlp", "type": "pii", "action": "mask"},
            {"id": "loop_guard", "stage": "behavior", "type": "loop_guard", "action": "flag"},
        ],
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


class _InnerRepository:
    def __init__(self) -> None:
        self.document = _policy()
        self.reloads = 0

    async def current(self) -> PolicyDocument:
        return self.document

    async def reload(self) -> PolicyDocument:
        self.reloads += 1
        return self.document

    async def status(self) -> dict:
        return {"version": 3, "status": "LOADED"}


def _build() -> tuple[OverriddenPolicyRepository, ProtectionService, _InnerRepository]:
    inner = _InnerRepository()
    protection = ProtectionService(InMemoryCacheRepository())
    return OverriddenPolicyRepository(inner, protection), protection, inner


async def test_without_overrides_the_inner_document_is_returned_unchanged() -> None:
    repository, _, inner = _build()

    assert await repository.current() is inner.document


async def test_override_replaces_enabled_only_for_the_targeted_rule() -> None:
    repository, protection, inner = _build()
    await protection.set_rule_override("pii_masking", False)

    rules = {rule.id: rule for rule in (await repository.current()).rules}

    assert rules["pii_masking"].enabled is False
    assert rules["loop_guard"].enabled is True
    assert all(rule.enabled for rule in inner.document.rules)


async def test_override_can_re_enable_a_rule_and_unknown_ids_are_ignored() -> None:
    repository, protection, _ = _build()
    await protection.set_rule_override("pii_masking", False)
    await protection.set_rule_override("ghost", False)
    await protection.set_rule_override("pii_masking", True)

    document = await repository.current()

    assert [rule.enabled for rule in document.rules] == [True, True]


async def test_status_adds_overrides_and_reload_delegates() -> None:
    repository, protection, inner = _build()
    await protection.set_rule_override("pii_masking", False)

    status = await repository.status()
    reloaded = await repository.reload()

    assert status["overrides"] == {"pii_masking": False}
    assert status["version"] == 3
    assert inner.reloads == 1
    assert next(r for r in reloaded.rules if r.id == "pii_masking").enabled is False
