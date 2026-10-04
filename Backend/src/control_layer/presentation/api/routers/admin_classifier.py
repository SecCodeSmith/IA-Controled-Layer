from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from control_layer.application.classifier.retrain_job_manager import (
    RetrainAlreadyRunningError,
    RetrainJob,
    RetrainJobNotFoundError,
)
from control_layer.application.services.dataset_curation_service import SampleNotFoundError
from control_layer.domain.models.enums import CallStatus
from control_layer.domain.models.training_sample import SampleStatus, TrainingSample
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.error_handlers import error_response
from control_layer.presentation.api.schemas.classifier import (
    ClassifierStatusResponse,
    CurateRequest,
    CurationSummary,
    RetrainJobResponse,
    RetrainRequest,
    SampleListResponse,
    SamplePatch,
)

router = APIRouter(prefix="/api/classifier", tags=["admin"], dependencies=AdminDeps)

_TERMINAL_EVENTS = frozenset({"retrain_complete", "retrain_failed"})

CurateBody = Annotated[CurateRequest, Body(default_factory=CurateRequest)]
RetrainBody = Annotated[RetrainRequest, Body(default_factory=RetrainRequest)]


def _not_found(exc: Exception) -> JSONResponse:
    return error_response(404, "not_found", CallStatus.BLOCKED, str(exc))


def _job_response(job: RetrainJob) -> RetrainJobResponse:
    return RetrainJobResponse.model_validate(job.model_dump())


@router.get("", response_model=ClassifierStatusResponse)
async def get_classifier_status(container: ContainerDep) -> ClassifierStatusResponse:
    status = await container.classifier_module.status.status()
    return ClassifierStatusResponse.model_validate(status.model_dump())


@router.get("/samples", response_model=SampleListResponse)
async def list_samples(
    container: ContainerDep, status: SampleStatus | None = None, limit: int = 100
) -> SampleListResponse:
    items = await container.classifier_module.status.list_samples(status, limit)
    return SampleListResponse(items=items)


@router.patch("/samples/{sample_id}", response_model=TrainingSample)
async def patch_sample(
    sample_id: str, patch: SamplePatch, container: ContainerDep
) -> TrainingSample | JSONResponse:
    try:
        return await container.classifier_module.status.patch_sample(
            sample_id, label=patch.label, status=patch.status
        )
    except SampleNotFoundError as exc:
        return _not_found(exc)


@router.post("/samples/curate", response_model=CurationSummary)
async def curate_samples(container: ContainerDep, request: CurateBody) -> CurationSummary:
    report = await container.classifier_module.curation.curate_pending(request.limit)
    return CurationSummary.model_validate(report.model_dump())


@router.post("/retrain", response_model=RetrainJobResponse)
async def start_retrain(
    container: ContainerDep, request: RetrainBody
) -> RetrainJobResponse | JSONResponse:
    try:
        job = await container.classifier_module.retrain_jobs.start(
            include_pending=request.include_pending, seed=request.seed
        )
    except RetrainAlreadyRunningError as exc:
        return error_response(409, "retrain_running", CallStatus.BLOCKED, str(exc))
    return _job_response(job)


@router.get("/retrain/{job_id}", response_model=RetrainJobResponse)
async def get_retrain_job(
    job_id: str, container: ContainerDep
) -> RetrainJobResponse | JSONResponse:
    try:
        return _job_response(container.classifier_module.retrain_jobs.get(job_id))
    except RetrainJobNotFoundError as exc:
        return _not_found(exc)


@router.get("/retrain/{job_id}/stream", response_model=None)
async def stream_retrain_job(
    job_id: str, container: ContainerDep
) -> EventSourceResponse | JSONResponse:
    try:
        subscription = container.classifier_module.retrain_jobs.subscribe(job_id)
    except RetrainJobNotFoundError as exc:
        return _not_found(exc)

    async def events() -> AsyncIterator[dict[str, str]]:
        async for event in subscription:
            yield {"event": event.event, "data": json.dumps(event.data, default=str)}
            if event.event in _TERMINAL_EVENTS:
                return

    return EventSourceResponse(events())
