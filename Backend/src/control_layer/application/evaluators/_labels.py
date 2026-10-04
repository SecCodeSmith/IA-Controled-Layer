from __future__ import annotations

from control_layer.domain.models.enums import Role

_ROLE_LABELS: dict[Role, str] = {
    Role.developer: "Developer",
    Role.hr: "HR",
    Role.finance: "Finance",
    Role.admin: "Administrator",
}


def role_label(role: Role) -> str:
    return _ROLE_LABELS.get(role, role.value.title())
