from __future__ import annotations

from pathlib import Path

import pytest

from control_layer.infrastructure.settings import Settings


def test_defaults_match_contract() -> None:
    settings = Settings(_env_file=None)

    assert settings.model_provider == "auto"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen2.5:7b"
    assert settings.judge_model == "qwen2.5:7b"
    assert settings.openai_base_url is None
    assert settings.openai_api_key is None
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.policy_file == "config/policy.yaml"
    assert settings.mcp_servers_file == "config/mcp_servers.yaml"
    assert settings.signatures_file == "config/attack_signatures.yaml"
    assert settings.signature_feed_url is None
    assert settings.users_file == "config/users.yaml"
    assert settings.alerts_xlsx == "alerts/alerts.xlsx"
    assert settings.audit_jsonl == "audit/calls.jsonl"
    expected_ml_path = "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib"
    assert settings.ml_model_path == expected_ml_path
    assert settings.jwt_secret == "dev-secret-change-me"
    assert settings.admin_token == "admin-dev-token"
    assert settings.cors_origins == "http://localhost:5173"
    assert settings.port == 8080


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTRL_MODEL_PROVIDER", "mock")
    monkeypatch.setenv("CTRL_OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("CTRL_PORT", "9090")
    monkeypatch.setenv("CTRL_JWT_SECRET", "test-secret")

    settings = Settings(_env_file=None)

    assert settings.model_provider == "mock"
    assert settings.ollama_model == "qwen2.5:3b"
    assert settings.port == 9090
    assert settings.jwt_secret == "test-secret"


def test_paths_resolved_relative_to_backend_dir() -> None:
    settings = Settings(_env_file=None)
    backend_dir = Path(__file__).resolve().parents[3]

    assert settings.base_dir == backend_dir
    assert settings.policy_file_path == backend_dir / "config" / "policy.yaml"
    assert settings.mcp_servers_file_path == backend_dir / "config" / "mcp_servers.yaml"
    assert settings.signatures_file_path == backend_dir / "config" / "attack_signatures.yaml"
    assert settings.users_file_path == backend_dir / "config" / "users.yaml"
    assert settings.alerts_xlsx_path == backend_dir / "alerts" / "alerts.xlsx"
    assert settings.audit_jsonl_path == backend_dir / "audit" / "calls.jsonl"


def test_absolute_path_override_is_not_rebased(tmp_path: Path) -> None:
    absolute_policy = tmp_path / "custom_policy.yaml"
    settings = Settings(_env_file=None, policy_file=str(absolute_policy))

    assert settings.policy_file_path == absolute_policy


def test_judge_model_env_override_independent_of_ollama_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CTRL_OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("CTRL_JUDGE_MODEL", "qwen2.5:7b")

    settings = Settings(_env_file=None)

    assert settings.ollama_model == "qwen2.5:3b"
    assert settings.judge_model == "qwen2.5:7b"
