from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ToolCallRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    server: str
    tool: str
    arguments: dict = Field(default_factory=dict)
    session_id: str | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.server}.{self.tool}"


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    server: str
    name: str
    qualified_name: str
    description: str
    input_schema: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    data_region: str | None = None
    scope: str


class ToolCallResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    content_text: str
    structured_content: dict | None = None
    is_error: bool = False
