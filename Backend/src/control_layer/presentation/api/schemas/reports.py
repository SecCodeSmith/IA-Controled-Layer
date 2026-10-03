from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OwaspCoverageRow(BaseModel):
    id: str
    title: str
    events: int
    status: str


class SecurityReportResponse(BaseModel):
    generated_at: datetime
    period: str
    summary: dict = {}
    top_rules: list[dict] = []
    top_users: list[dict] = []
    owasp_coverage: list[OwaspCoverageRow] = []
    recommendations: list[str] = []
    markdown: str
