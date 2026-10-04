from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from control_layer.application.use_cases.admin.resources_view import ResourceMatrixUseCase
from control_layer.application.use_cases.admin.workbench import (
    ProviderDescriber,
    WorkbenchTraceUseCase,
)
from control_layer.domain.models.provider import ProviderInfo


@dataclass
class WorkbenchModule:
    trace: WorkbenchTraceUseCase
    matrix: ResourceMatrixUseCase


class _ConfiguredProvider:
    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def describe(self) -> ProviderInfo:
        return ProviderInfo(name=self._settings.model_provider, model=self._settings.ollama_model)


def _provider_for(dependencies: dict[str, Any]) -> ProviderDescriber:
    provider = dependencies.get("model_provider")
    return provider if provider is not None else _ConfiguredProvider(dependencies["settings"])


def build_workbench_module(**dependencies: Any) -> WorkbenchModule:
    return WorkbenchModule(
        trace=WorkbenchTraceUseCase(
            pipeline=dependencies["pipeline"],
            issue_token=dependencies["issue_token"],
            session_service=dependencies["session_service"],
            audit_service=dependencies["audit_service"],
            risk_service=dependencies["risk_service"],
            call_ids=dependencies["call_ids"],
            tool_call_use_case=dependencies["tool_call"],
            audit_repository=dependencies["audit_repository"],
            model_provider=_provider_for(dependencies),
        ),
        matrix=ResourceMatrixUseCase(
            policy_repository=dependencies["policy_repository"],
            tool_catalog=dependencies["tool_catalog"],
        ),
    )
