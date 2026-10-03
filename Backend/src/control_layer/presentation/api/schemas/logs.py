from __future__ import annotations

from pydantic import BaseModel


class ClearLogsResponse(BaseModel):
    ok: bool = True
    cleared: list[str]
