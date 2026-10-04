from __future__ import annotations

from control_layer.domain.models.chat import PROMPT_TURN_SEPARATOR
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.enums import InterceptionPoint


def injection_text(ctx: ProcessingContext) -> str:
    text = ctx.current_text
    if ctx.point == InterceptionPoint.prompt and PROMPT_TURN_SEPARATOR in text:
        return text.rsplit(PROMPT_TURN_SEPARATOR, 1)[-1]
    return text
