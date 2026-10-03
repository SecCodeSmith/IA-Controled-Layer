from __future__ import annotations

import yaml

from control_layer.domain.models.rule import Rule


def rule_to_yaml(rule: Rule) -> str:
    data: dict = {"id": rule.id}
    if rule.on:
        data["on"] = rule.on[0].value if len(rule.on) == 1 else [point.value for point in rule.on]
    if rule.match is not None:
        data["match"] = rule.match
    if rule.detect is not None:
        data["detect"] = rule.detect
    data["type"] = rule.type
    data["action"] = rule.action.value
    if rule.owasp:
        data["owasp"] = rule.owasp
    return yaml.safe_dump([data], sort_keys=False, default_flow_style=None)
