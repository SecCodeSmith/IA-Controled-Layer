"""Demo agent configuration, environment prefix `AGENT_`."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_")

    control_layer_url: str = "http://localhost:8080"
    port: int = 8090
    max_iterations: int = 6
    temperature: float = 0.0
    request_timeout_s: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
