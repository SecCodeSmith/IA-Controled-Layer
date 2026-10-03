from __future__ import annotations

from typing import Any, Protocol

from control_layer.domain.models.policy import PolicyDocument


class PolicyRepository(Protocol):
    async def current(self) -> PolicyDocument: ...

    async def reload(self) -> PolicyDocument: ...

    async def status(self) -> dict[str, Any]: ...
