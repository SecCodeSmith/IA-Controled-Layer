from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any

from control_layer.domain.exceptions import PolicyValidationError
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule

RESTORABLE_KINDS = frozenset({"email", "phone", "pesel", "iban", "pan"})
DEFAULT_TTL_S = 28800
_PATTERN_RE = re.compile(r"^[A-Za-z0-9_.*?-]+$")


@dataclass(frozen=True, slots=True)
class VaultConfig:
    ttl_s: int = DEFAULT_TTL_S
    restore: dict[str, tuple[str, ...]] = field(default_factory=dict)


def parse_vault_config(raw: Any, rule_id: str) -> VaultConfig:
    if not isinstance(raw, dict):
        raise PolicyValidationError(f"rule '{rule_id}': vault must be a mapping")
    ttl = raw.get("ttl_s", DEFAULT_TTL_S)
    if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
        raise PolicyValidationError(f"rule '{rule_id}': vault.ttl_s must be a positive integer")
    restore_raw = raw.get("restore") or {}
    if not isinstance(restore_raw, dict):
        raise PolicyValidationError(f"rule '{rule_id}': vault.restore must be a mapping")
    restore: dict[str, tuple[str, ...]] = {}
    for kind, patterns in restore_raw.items():
        if kind not in RESTORABLE_KINDS:
            raise PolicyValidationError(
                f"rule '{rule_id}': vault.restore kind '{kind}' is not restorable"
            )
        if isinstance(patterns, str):
            patterns = [patterns]
        if not isinstance(patterns, list) or not all(
            isinstance(p, str) and _PATTERN_RE.match(p) for p in patterns
        ):
            raise PolicyValidationError(
                f"rule '{rule_id}': vault.restore.{kind} must be a list of tool patterns"
            )
        restore[kind] = tuple(patterns)
    return VaultConfig(ttl_s=ttl, restore=restore)


def vault_config_for_rule(rule: Rule) -> VaultConfig | None:
    raw = rule.params.get("vault")
    if not raw:
        return None
    return parse_vault_config(raw, rule.id)


def restorable_kinds_for_tool(policy: PolicyDocument, qualified_name: str) -> frozenset[str]:
    kinds: set[str] = set()
    for rule in policy.rules:
        if not rule.enabled:
            continue
        config = vault_config_for_rule(rule)
        if config is None:
            continue
        for kind, patterns in config.restore.items():
            if any(fnmatch(qualified_name, pattern) for pattern in patterns):
                kinds.add(kind)
    return frozenset(kinds)
