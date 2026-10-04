from __future__ import annotations

from control_layer.application.use_cases.admin.workbench_views import (
    JudgeVerdict,
    JudgeView,
    ResourceMatrixView,
    ResourceView,
    StageView,
    ToolCallSpec,
    TraceInput,
    TraceKind,
    TraceView,
    ViolationView,
)

__all__ = [
    "JudgeVerdict",
    "JudgeView",
    "ResourceMatrixResponse",
    "ResourceView",
    "StageView",
    "ToolCallSpec",
    "TraceKind",
    "TraceRequest",
    "TraceResponse",
    "ViolationView",
]


class TraceRequest(TraceInput):
    pass


class TraceResponse(TraceView):
    pass


class ResourceMatrixResponse(ResourceMatrixView):
    pass
