from __future__ import annotations

from control_layer.application.detectors.masking import MaskResult, apply, detect
from control_layer.application.dlp.session_vault import SessionVault
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import RuleAction
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.policy.vault import vault_config_for_rule

_LABELS: dict[str, tuple[str, str]] = {
    "email": ("email address", "email addresses"),
    "phone": ("phone number", "phone numbers"),
    "pesel": ("PESEL number", "PESEL numbers"),
    "iban": ("IBAN number", "IBAN numbers"),
    "pan": ("card number", "card numbers"),
    "api_key": ("API key", "API keys"),
    "private_key": ("private key", "private keys"),
    "jwt": ("JWT token", "JWT tokens"),
}


def _label(kind: str, count: int) -> str:
    singular, plural = _LABELS.get(kind, (kind, kind))
    return singular if count == 1 else plural


class DetectorsEvaluator:
    def __init__(self, vault: SessionVault | None = None) -> None:
        self._vault = vault

    async def _mask(self, rule: Rule, ctx: ProcessingContext, kinds: list[str]) -> MaskResult:
        matches = detect(ctx.current_text, kinds)
        config = vault_config_for_rule(rule)
        vault_disabled = self._vault is None or config is None or ctx.identity is None
        if vault_disabled or not ctx.session_id or rule.action == RuleAction.block:
            return apply(ctx.current_text, matches)
        placeholders: dict[tuple[str, str], str] = {}
        for match in matches:
            key = (match.kind, match.value)
            if match.kind in config.restore and key not in placeholders:
                placeholders[key] = await self._vault.placeholder_for(
                    ctx.session_id, match.kind, match.value, config.ttl_s, sub=ctx.identity.sub
                )
        return apply(ctx.current_text, matches, placeholders)

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        kinds = rule.detect or []
        if not kinds:
            return RuleOutcome(matched=False)

        result = await self._mask(rule, ctx, kinds)
        if not result.counts:
            return RuleOutcome(matched=False)

        ordered_kinds = [kind for kind in kinds if kind in result.counts]
        joined = " and ".join(
            f"{result.counts[kind]} {_label(kind, result.counts[kind])}" for kind in ordered_kinds
        )

        if rule.action == RuleAction.block:
            return RuleOutcome(
                matched=True,
                reason=f"{joined} found in the {ctx.point.value}",
                evidence=ordered_kinds,
            )

        return RuleOutcome(
            matched=True,
            masked_text=result.text,
            reason=f"{joined} masked in the {ctx.point.value}",
            evidence=ordered_kinds,
        )
