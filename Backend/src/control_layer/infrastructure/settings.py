from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CTRL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_provider: str = "auto"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    judge_model: str = "qwen2.5:7b"
    openai_base_url: str | None = None
    openai_api_key: str | None = None

    redis_url: str = "redis://localhost:6379/0"

    policy_file: str = "config/policy.yaml"
    mcp_servers_file: str = "config/mcp_servers.yaml"
    signatures_file: str = "config/attack_signatures.yaml"
    signature_feed_url: str | None = None
    users_file: str = "config/users.yaml"

    alerts_xlsx: str = "alerts/alerts.xlsx"
    audit_jsonl: str = "audit/calls.jsonl"

    ml_model_path: str = "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib"

    jwt_secret: str = "dev-secret-change-me"
    admin_token: str = "admin-dev-token"

    cors_origins: str = "http://localhost:5173"
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
    port: int = 8080

    @property
    def base_dir(self) -> Path:
        return _BACKEND_DIR

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.base_dir / path

    @cached_property
    def policy_file_path(self) -> Path:
        return self._resolve(self.policy_file)

    @cached_property
    def mcp_servers_file_path(self) -> Path:
        return self._resolve(self.mcp_servers_file)

    @cached_property
    def signatures_file_path(self) -> Path:
        return self._resolve(self.signatures_file)

    @cached_property
    def users_file_path(self) -> Path:
        return self._resolve(self.users_file)

    @cached_property
    def alerts_xlsx_path(self) -> Path:
        return self._resolve(self.alerts_xlsx)

    @cached_property
    def audit_jsonl_path(self) -> Path:
        return self._resolve(self.audit_jsonl)

    @cached_property
    def ml_model_path_resolved(self) -> Path:
        return self._resolve(self.ml_model_path)
