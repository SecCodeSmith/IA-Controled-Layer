from __future__ import annotations

import re

from control_layer.domain.ports.audit_repository import AuditRepository

_CALL_ID_RE = re.compile(r"^c_(\d+)$")


async def highest_call_id(audit_repository: AuditRepository) -> int:
    highest = 0
    for row in await audit_repository.export_rows():
        match = _CALL_ID_RE.match(str(row.get("call_id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest
