from __future__ import annotations

from pydantic import BaseModel


class DemoResetResponse(BaseModel):
    ok: bool = True
