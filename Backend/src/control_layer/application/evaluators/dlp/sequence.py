from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.models.session import SessionState
from control_layer.domain.models.tool import ToolDescriptor


class SequenceEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if rule.match is None:
            return RuleOutcome(matched=False)

        sequence = rule.match.get("sequence")
        if not sequence or len(sequence) != 2:
            return RuleOutcome(matched=False)
        tag_a, tag_b = sequence

        descriptor: ToolDescriptor | None = ctx.metadata.get("tool_descriptor")
        session_state: SessionState | None = ctx.metadata.get("session_state")
        if descriptor is None or session_state is None:
            return RuleOutcome(matched=False)

        if tag_b not in descriptor.tags:
            return RuleOutcome(matched=False)

        if tag_a in session_state.tags_seen or session_state.tainted:
            return RuleOutcome(
                matched=True,
                reason="Possible exfiltration after reading external doc",
                evidence=[tag_a, tag_b],
            )

        return RuleOutcome(matched=False)
