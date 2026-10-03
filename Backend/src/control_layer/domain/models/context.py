from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.chat import ChatCompletionRequest
from control_layer.domain.models.enums import InterceptionPoint
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolCallRequest


class ProcessingContext(BaseModel):
    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    identity: Identity | None
    point: InterceptionPoint
    text: str
    masked_text: str | None = None
    tool_call: ToolCallRequest | None = None
    chat: ChatCompletionRequest | None = None
    session_id: str
    call_id: str
    metadata: dict = Field(default_factory=dict)

    @property
    def current_text(self) -> str:
        return self.masked_text if self.masked_text is not None else self.text
