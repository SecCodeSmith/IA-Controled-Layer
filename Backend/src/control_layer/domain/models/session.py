from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionState(BaseModel):
    model_config = ConfigDict(frozen=False)

    session_id: str
    tags_seen: list[str] = Field(default_factory=list)
    tainted: bool = False
    call_hashes: list[str] = Field(default_factory=list)
