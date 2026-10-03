from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.signature import Signature


class SignatureFeed(Protocol):
    async def signatures(self) -> list[Signature]: ...

    async def reload(self) -> None: ...
