from __future__ import annotations

from control_layer.application.dlp.session_vault import SessionVault
from tests.unit.application.evaluators.conftest import FakeCacheRepository

EMAIL = "k.wrona@example.com"


def _vault() -> tuple[SessionVault, FakeCacheRepository]:
    cache = FakeCacheRepository()
    return SessionVault(cache), cache


async def test_placeholder_is_stable_within_a_session() -> None:
    vault, _ = _vault()
    first = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="u1")
    again = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="u1")
    other = await vault.placeholder_for("s1", "email", "a@b.pl", 60, sub="u1")
    assert first == again == "[EMAIL_1]"
    assert other == "[EMAIL_2]"


async def test_counters_are_per_kind_and_per_session() -> None:
    vault, _ = _vault()
    assert await vault.placeholder_for("s1", "email", EMAIL, 60, sub="u1") == "[EMAIL_1]"
    phone = await vault.placeholder_for("s1", "phone", "+48 600 100 200", 60, sub="u1")
    assert phone == "[PHONE_1]"
    assert await vault.placeholder_for("s2", "email", "a@b.pl", 60, sub="u1") == "[EMAIL_1]"


async def test_ttl_is_passed_to_the_cache() -> None:
    vault, cache = _vault()
    await vault.placeholder_for("s1", "email", EMAIL, 1234, sub="u1")
    vault_keys = [key for key in cache.store if key.startswith("vault:")]
    assert len(vault_keys) == 3
    assert {cache.ttls[key] for key in vault_keys} == {1234}


async def test_restore_replaces_allowed_kinds_only() -> None:
    vault, _ = _vault()
    email = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="u1")
    phone = await vault.placeholder_for("s1", "phone", "+48 600 100 200", 60, sub="u1")
    text, count = await vault.restore("s1", f"to {email} call {phone}", {"email"}, sub="u1")
    assert text == f"to {EMAIL} call {phone}"
    assert count == 1


async def test_restore_ignores_other_sessions_and_unknown_placeholders() -> None:
    vault, _ = _vault()
    await vault.placeholder_for("s1", "email", EMAIL, 60, sub="u1")
    text, count = await vault.restore("s2", "to [EMAIL_1] and [EMAIL_9]", {"email"}, sub="u1")
    assert text == "to [EMAIL_1] and [EMAIL_9]"
    assert count == 0
    text, count = await vault.restore("s1", "to [EMAIL_9] [FOO_1]", {"email"}, sub="u1")
    assert (text, count) == ("to [EMAIL_9] [FOO_1]", 0)


async def test_restore_value_walks_nested_structures() -> None:
    vault, _ = _vault()
    email = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="u1")
    arguments = {"to": email, "cc": [email, {"x": f"hi {email}"}], "n": 3, "flag": True}
    restored, count = await vault.restore_value("s1", arguments, {"email"}, sub="u1")
    assert restored == {"to": EMAIL, "cc": [EMAIL, {"x": f"hi {EMAIL}"}], "n": 3, "flag": True}
    assert count == 3
    assert arguments["to"] == email


async def test_same_session_id_with_a_different_sub_is_not_restored() -> None:
    vault, _ = _vault()
    placeholder = await vault.placeholder_for("s1", "email", EMAIL, 60, sub="u1")
    text, count = await vault.restore("s1", placeholder, {"email"}, sub="intruder")
    assert (text, count) == (placeholder, 0)
    assert await vault.placeholder_for("s1", "email", "a@b.pl", 60, sub="intruder") == "[EMAIL_1]"
