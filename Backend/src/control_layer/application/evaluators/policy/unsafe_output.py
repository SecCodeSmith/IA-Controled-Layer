from __future__ import annotations

import re

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule

_APPLICABLE_POINTS = (InterceptionPoint.response, InterceptionPoint.tool_result)

_UNSAFE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"curl\s.*\|\s*(sh|bash)\b", re.IGNORECASE),
    re.compile(r"rm\s+-rf\b", re.IGNORECASE),
]
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://([^)/]+))[^)]*\)", re.IGNORECASE)


class UnsafeOutputEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if ctx.point not in _APPLICABLE_POINTS:
            return RuleOutcome(matched=False)

        text = ctx.current_text
        for pattern in _UNSAFE_PATTERNS:
            match = pattern.search(text)
            if match is not None:
                return RuleOutcome(
                    matched=True,
                    reason="Unsafe content in model output",
                    evidence=[match.group()],
                )

        allowed_domains = rule.params.get("allowed_domains", [])
        for link_match in _MARKDOWN_LINK_RE.finditer(text):
            domain = link_match.group(2)
            is_allowed = any(
                domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains
            )
            if is_allowed:
                continue
            return RuleOutcome(
                matched=True,
                reason="Unsafe content in model output",
                evidence=[link_match.group(1)],
            )

        return RuleOutcome(matched=False)
