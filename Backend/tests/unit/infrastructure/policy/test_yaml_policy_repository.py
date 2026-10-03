from __future__ import annotations

from pathlib import Path

import pytest

from control_layer.domain.exceptions import PolicyValidationError
from control_layer.domain.models.policy import PolicyDocument
from control_layer.infrastructure.policy.yaml_policy_repository import YamlPolicyRepository

REAL_POLICY_FILE = Path(__file__).resolve().parents[4] / "config" / "policy.yaml"

VALID_YAML = """
version: 1
profile: balanced
models:
  allowed: [mock]
  pricing: {}
roles:
  developer: { mcp_servers: [github] }
locations: {}
rules:
  - { id: pii_masking, on: response, detect: [email], action: mask, owasp: [LLM02] }
budgets:
  per_user_tokens: 10000
  per_user_cost_usd: 1.0
  max_tokens_per_request: 2048
  upstream_timeout_s: 30
  warn_at_percent: 80
  on_exceeded: block
"""

VALID_YAML_V2 = VALID_YAML.replace("version: 1", "version: 2")

INVALID_YAML = "version: [this is: not, valid"


@pytest.mark.skipif(not REAL_POLICY_FILE.exists(), reason="Backend/config/policy.yaml not present")
async def test_loads_real_sample_policy_file() -> None:
    repo = YamlPolicyRepository(REAL_POLICY_FILE)

    document = await repo.current()

    assert isinstance(document, PolicyDocument)
    assert document.version == 3
    status = await repo.status()
    assert status["status"] == "LOADED"
    assert status["error"] is None


async def test_loads_valid_yaml_from_tmp_file(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")
    repo = YamlPolicyRepository(path)

    document = await repo.current()

    assert document.version == 1
    status = await repo.status()
    assert status["version"] == 1
    assert status["status"] == "LOADED"
    assert status["source"] == str(path)
    assert "per_user_tokens" in status["raw_yaml"]


async def test_reload_picks_up_new_valid_version(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")
    repo = YamlPolicyRepository(path)
    await repo.current()

    path.write_text(VALID_YAML_V2, encoding="utf-8")
    document = await repo.reload()

    assert document.version == 2
    status = await repo.status()
    assert status["version"] == 2
    assert status["status"] == "LOADED"


async def test_invalid_yaml_keeps_last_good_with_error_status(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")
    repo = YamlPolicyRepository(path)
    await repo.current()

    path.write_text(INVALID_YAML, encoding="utf-8")
    document = await repo.reload()

    assert document.version == 1
    status = await repo.status()
    assert status["status"] == "ERROR"
    assert status["error"] is not None
    assert status["version"] == 1


async def test_initial_load_failure_with_no_prior_document_raises(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text(INVALID_YAML, encoding="utf-8")
    repo = YamlPolicyRepository(path)

    status = await repo.status()
    assert status["status"] == "ERROR"

    with pytest.raises(PolicyValidationError):
        await repo.current()


async def test_missing_budgets_key_is_invalid(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("version: 1\n", encoding="utf-8")
    repo = YamlPolicyRepository(path)

    status = await repo.status()
    assert status["status"] == "ERROR"
    assert "budgets" in status["error"]
