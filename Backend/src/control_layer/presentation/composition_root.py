from __future__ import annotations

import functools
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from control_layer.application.audit.rule_yaml import rule_to_yaml
from control_layer.application.auth.identity_service import IdentityService
from control_layer.application.evaluators import build_evaluators
from control_layer.application.evaluators.dependencies import EvaluatorDependencies
from control_layer.application.events.feed_broadcaster import FeedBroadcaster
from control_layer.application.gateway.credential_resolver import GatewayCredentialResolver
from control_layer.application.pipeline.processing_pipeline import ProcessingPipeline
from control_layer.application.pipeline.stages.audit import AuditStage
from control_layer.application.pipeline.stages.authorization import AuthorizationStage
from control_layer.application.pipeline.stages.behavior import BehaviorStage
from control_layer.application.pipeline.stages.dlp import DlpStage
from control_layer.application.pipeline.stages.identity import IdentityStage
from control_layer.application.pipeline.stages.policy import PolicyStage
from control_layer.application.pipeline.stages.resource import ResourceStage
from control_layer.application.policy.overridden_policy_repository import (
    OverriddenPolicyRepository,
)
from control_layer.application.reports.security_report import SecurityReportUseCase
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.application.selftest.attack_run_manager import AttackRunManager
from control_layer.application.services.alert_factory import AlertFactory
from control_layer.application.services.approval_service import ApprovalService
from control_layer.application.services.audit_service import AuditService
from control_layer.application.services.budget_service import BudgetService
from control_layer.application.services.call_id_generator import CallIdGenerator
from control_layer.application.services.call_id_seeding import highest_call_id
from control_layer.application.services.circuit_breaker_service import CircuitBreakerService
from control_layer.application.services.model_selection_service import ModelSelectionService
from control_layer.application.services.protection_service import (
    ProtectionService,
    current_protection,
)
from control_layer.application.services.risk_service import RiskService
from control_layer.application.services.session_service import SessionService
from control_layer.application.services.tool_catalog import ToolCatalog
from control_layer.application.telemetry.metrics_collector import MetricsCollector
from control_layer.application.use_cases.admin.alerts import ListAlertsUseCase
from control_layer.application.use_cases.admin.audit import (
    GetCallDetailUseCase,
    ListAuditUseCase,
)
from control_layer.application.use_cases.admin.clear_logs import ClearLogsUseCase
from control_layer.application.use_cases.admin.exports import (
    ExportAlertsUseCase,
    ExportAuditUseCase,
)
from control_layer.application.use_cases.admin.feed import ListFeedUseCase
from control_layer.application.use_cases.admin.health import (
    ClassifierStatus,
    GatewayInfo,
    GetHealthUseCase,
    HealthView,
    McpServerStatus,
    PolicyStatus,
)
from control_layer.application.use_cases.admin.policy_view import (
    GetPolicyViewUseCase,
    ReloadPolicyUseCase,
)
from control_layer.application.use_cases.admin.protection import ManageProtectionUseCase
from control_layer.application.use_cases.admin.reset import ResetDemoUseCase
from control_layer.application.use_cases.admin.stats import StatsCalculator
from control_layer.application.use_cases.admin.stream_feed import StreamFeedUseCase
from control_layer.application.use_cases.execute_approval import ExecuteApprovalUseCase
from control_layer.application.use_cases.get_approval import GetApprovalUseCase
from control_layer.application.use_cases.get_me import GetMeUseCase
from control_layer.application.use_cases.handle_chat_completion import (
    HandleChatCompletionUseCase,
)
from control_layer.application.use_cases.handle_tool_call import HandleToolCallUseCase
from control_layer.application.use_cases.issue_token import IssueTokenUseCase
from control_layer.application.use_cases.list_tools import ListToolsUseCase
from control_layer.application.use_cases.list_users import ListUsersUseCase
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.models.enums import StageName
from control_layer.domain.ports.policy_repository import PolicyRepository
from control_layer.infrastructure.alerts.composite_alert_sink import CompositeAlertSink
from control_layer.infrastructure.alerts.excel_alert_sink import ExcelAlertSink
from control_layer.infrastructure.alerts.in_memory_alert_store import InMemoryAlertStore
from control_layer.infrastructure.audit.jsonl_audit_repository import JsonlAuditRepository
from control_layer.infrastructure.auth.hmac_token_verifier import HmacTokenVerifier
from control_layer.infrastructure.cache.cache_factory import build_cache_repository
from control_layer.infrastructure.mcp.mcp_client_gateway import McpClientGateway
from control_layer.infrastructure.mcp.mcp_server_registry import McpServerRegistry
from control_layer.infrastructure.policy.policy_file_watcher import PolicyFileWatcher
from control_layer.infrastructure.policy.yaml_policy_repository import YamlPolicyRepository
from control_layer.infrastructure.providers.ollama_model_directory import OllamaModelDirectory
from control_layer.infrastructure.providers.provider_factory import (
    build_model_provider,
    build_provider_for,
)
from control_layer.infrastructure.providers.switchable_provider import SwitchableModelProvider
from control_layer.infrastructure.repositories.approval_repository import (
    CacheApprovalRepository,
)
from control_layer.infrastructure.repositories.budget_repository import CacheBudgetRepository
from control_layer.infrastructure.repositories.risk_repository import CacheRiskRepository
from control_layer.infrastructure.repositories.session_repository import (
    CacheSessionRepository,
)
from control_layer.infrastructure.settings import Settings
from control_layer.infrastructure.signatures.yaml_signature_feed import YamlSignatureFeed
from control_layer.infrastructure.users.yaml_user_repository import YamlUserRepository
from control_layer.ml.classifier import NullPromptClassifier, SklearnPromptClassifier
from control_layer.presentation.policy_alerts import PolicyReloadNotifier
from control_layer.presentation.selftest.executor_factory import build_executor_factory
from control_layer.presentation.wiring.classifier_module import (
    ClassifierModule,
    build_classifier_module,
)
from control_layer.presentation.wiring.workbench_module import (
    WorkbenchModule,
    build_workbench_module,
)

logger = logging.getLogger(__name__)

_RUNTIME_STATE_PREFIXES = (
    "decision:", "rate:", "loop:", "cb:", "quarantine:", "seen:", "calls:",
    "budget:", "session:", "risk:", "approval:",
)


class MeteredAuditRepository:
    def __init__(
        self,
        inner: JsonlAuditRepository,
        metrics: MetricsCollector,
        policy_repository: PolicyRepository,
    ) -> None:
        self._inner = inner
        self._metrics = metrics
        self._policy_repository = policy_repository

    async def _with_rule_yaml(self, record: CallRecord) -> CallRecord:
        rule_id = record.decision.rule_id
        if record.matched_rule_yaml is not None or rule_id is None:
            return record
        policy = await self._policy_repository.current()
        rule = next((r for r in policy.rules if r.id == rule_id), None)
        if rule is None:
            return record
        return record.model_copy(update={"matched_rule_yaml": rule_to_yaml(rule)})

    async def append(self, record: CallRecord) -> None:
        record = await self._with_rule_yaml(record)
        await self._inner.append(record)
        self._metrics.record(record)

    async def list_recent(self, limit: int = 100) -> list[Any]:
        return await self._inner.list_recent(limit)

    async def get(self, call_id: str) -> Any:
        return await self._inner.get(call_id)

    async def clear(self) -> None:
        await self._inner.clear()

    async def export_rows(self) -> list[dict[str, Any]]:
        return await self._inner.export_rows()


class MeteredPipeline(ProcessingPipeline):
    def __init__(self, *args: Any, metrics: MetricsCollector, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._metrics = metrics

    async def run(self, ctx: Any) -> Any:
        decision = await super().run(ctx)
        cacheable = [
            r for r in decision.stage_results if r.stage in (StageName.dlp, StageName.policy)
        ]
        if cacheable:
            self._metrics.record_cache(all(r.cache_hit for r in cacheable))
        return decision


@dataclass
class Container:
    settings: Settings
    cache: Any
    cache_mode: str
    policy_repository: OverriddenPolicyRepository
    protection: ProtectionService
    policy_watcher: PolicyFileWatcher
    policy_notifier: PolicyReloadNotifier
    call_ids: CallIdGenerator
    signature_watcher: PolicyFileWatcher
    signature_feed: YamlSignatureFeed
    user_repository: YamlUserRepository
    token_verifier: HmacTokenVerifier
    model_provider: SwitchableModelProvider
    model_selection: ModelSelectionService
    model_directory: OllamaModelDirectory
    gateway_credentials: GatewayCredentialResolver
    mcp_registry: McpServerRegistry
    mcp_gateway: McpClientGateway
    classifier: Any
    evaluator_registry: EvaluatorRegistry
    stages: list[Any]
    pipeline: ProcessingPipeline
    identity_service: IdentityService
    tool_catalog: ToolCatalog
    audit_repository: MeteredAuditRepository
    alert_store: InMemoryAlertStore
    feed_broadcaster: FeedBroadcaster
    metrics_collector: MetricsCollector
    list_users: ListUsersUseCase
    issue_token: IssueTokenUseCase
    get_me: GetMeUseCase
    list_tools: ListToolsUseCase
    chat_completion: HandleChatCompletionUseCase
    tool_call: HandleToolCallUseCase
    get_approval: GetApprovalUseCase
    execute_approval: ExecuteApprovalUseCase
    list_feed: ListFeedUseCase
    stream_feed: StreamFeedUseCase
    list_audit: ListAuditUseCase
    call_detail: GetCallDetailUseCase
    export_audit: ExportAuditUseCase
    list_alerts: ListAlertsUseCase
    export_alerts: ExportAlertsUseCase
    stats: StatsCalculator
    policy_view: GetPolicyViewUseCase
    reload_policy: ReloadPolicyUseCase
    security_report: SecurityReportUseCase
    reset_demo: ResetDemoUseCase
    clear_logs: ClearLogsUseCase
    manage_protection: ManageProtectionUseCase
    health: GetHealthUseCase
    attack_runs: AttackRunManager
    reset_runtime_state: Callable[[], Awaitable[None]]
    classifier_module: ClassifierModule
    workbench: WorkbenchModule


def _load_classifier(settings: Settings) -> Any:
    try:
        return SklearnPromptClassifier.load(str(settings.ml_model_path_resolved))
    except Exception as exc:
        logger.warning("Prompt classifier unavailable (%s); using null classifier", exc)
        return NullPromptClassifier()


async def build_container(settings: Settings) -> Container:
    cache_result = await build_cache_repository(settings)
    cache = cache_result.repository

    file_policy_repository = YamlPolicyRepository(settings.policy_file_path)
    protection = ProtectionService(cache)
    policy_repository = OverriddenPolicyRepository(file_policy_repository, protection)
    signature_feed = YamlSignatureFeed(settings.signatures_file_path)
    user_repository = YamlUserRepository(settings.users_file_path)
    token_verifier = HmacTokenVerifier(settings.jwt_secret)
    model_provider = SwitchableModelProvider(await build_model_provider(settings))
    model_directory = OllamaModelDirectory(settings.ollama_base_url)
    model_selection = ModelSelectionService(
        model_provider,
        model_directory,
        functools.partial(build_provider_for, settings),
        policy_repository,
        cache,
    )
    classifier = _load_classifier(settings)

    mcp_registry = McpServerRegistry(settings.mcp_servers_file_path, settings.base_dir)
    mcp_gateway = McpClientGateway(mcp_registry)

    metrics = MetricsCollector()
    feed_broadcaster = FeedBroadcaster()
    canary_token = f"CANARY-{uuid.uuid4().hex[:12]}"

    classifier_module = build_classifier_module(
        settings, cache, model_provider, signature_feed, feed_broadcaster
    )

    registry = EvaluatorRegistry()
    evaluators = build_evaluators(
        EvaluatorDependencies(
            cache=cache,
            signature_feed=signature_feed,
            classifier=classifier,
            model_provider=model_provider,
            canary_token=canary_token,
            judge_model=settings.judge_model,
            tree_classifier=classifier_module.tree_classifier,
            sampler=classifier_module.sampler,
        )
    )
    for rule_type, evaluator in evaluators.items():
        registry.register(rule_type, evaluator)
    registry.register("llm_judge", classifier_module.wrap_judge(evaluators["llm_judge"]))

    approval_repository = CacheApprovalRepository(cache)
    budget_repository = CacheBudgetRepository(cache, policy_repository)
    risk_repository = CacheRiskRepository(cache)
    session_repository = CacheSessionRepository(cache)

    alert_store = InMemoryAlertStore()
    alert_sink = CompositeAlertSink([ExcelAlertSink(settings.alerts_xlsx_path)])
    audit_repository = MeteredAuditRepository(
        JsonlAuditRepository(settings.audit_jsonl_path), metrics, policy_repository
    )

    stages = [
        IdentityStage(token_verifier, user_repository),
        AuthorizationStage(registry),
        DlpStage(registry),
        PolicyStage(registry),
        BehaviorStage(registry, session_repository),
        ResourceStage(budget_repository),
        AuditStage(feed_broadcaster),
    ]
    pipeline = MeteredPipeline(
        stages, cache, policy_repository, metrics=metrics, protection=protection
    )

    identity_service = IdentityService(token_verifier, user_repository)
    tool_catalog = ToolCatalog(mcp_gateway, policy_repository)
    call_ids = CallIdGenerator(cache)
    budget_service = BudgetService(budget_repository)
    session_service = SessionService(session_repository)
    approval_service = ApprovalService(approval_repository, cache)
    circuit_breaker = CircuitBreakerService(cache, alert_sink, policy_repository)
    risk_service = RiskService(risk_repository)
    audit_service = AuditService(
        audit_repository,
        alert_sink,
        alert_store,
        feed_broadcaster,
        AlertFactory(),
        policy_repository,
    )

    chat_completion = HandleChatCompletionUseCase(
        pipeline,
        identity_service,
        model_provider,
        budget_service,
        session_service,
        audit_service,
        circuit_breaker,
        risk_service,
        call_ids,
        policy_repository,
        canary_token,
    )
    tool_call = HandleToolCallUseCase(
        pipeline,
        tool_catalog,
        mcp_gateway,
        approval_service,
        session_service,
        audit_service,
        circuit_breaker,
        risk_service,
        call_ids,
        policy_repository,
        model_provider,
    )
    execute_approval = ExecuteApprovalUseCase(
        approval_service, identity_service, tool_call, audit_service, call_ids, model_provider
    )

    stats = StatsCalculator(
        audit_repository,
        budget_repository,
        risk_repository,
        metrics,
        policy_repository,
        model_provider,
        user_repository,
        protection,
    )
    policy_view = GetPolicyViewUseCase(policy_repository)

    policy_notifier = PolicyReloadNotifier(
        file_policy_repository, alert_sink, alert_store, feed_broadcaster.publish
    )

    async def reload_signatures() -> None:
        await signature_feed.reload()

    issue_token = IssueTokenUseCase(user_repository, token_verifier)
    gateway_credentials = GatewayCredentialResolver(
        issue_token, user_repository, settings.gateway_default_user
    )

    async def reset_runtime_state() -> None:
        for prefix in _RUNTIME_STATE_PREFIXES:
            await cache.flush(prefix)

    clear_logs = ClearLogsUseCase(
        audit_repository, alert_store, alert_sink, metrics, call_ids, feed_broadcaster.publish
    )

    attack_runs = AttackRunManager(
        build_executor_factory(
            settings, chat_completion, tool_call, execute_approval, issue_token, token_verifier,
            model_provider,
            reset_runtime_state,
        ),
        feed_broadcaster,
    )

    workbench = build_workbench_module(
        settings=settings,
        pipeline=pipeline,
        identity_service=identity_service,
        issue_token=issue_token,
        token_verifier=token_verifier,
        user_repository=user_repository,
        tool_call=tool_call,
        tool_catalog=tool_catalog,
        audit_service=audit_service,
        audit_repository=audit_repository,
        risk_service=risk_service,
        session_service=session_service,
        budget_service=budget_service,
        call_ids=call_ids,
        policy_repository=policy_repository,
        classifier_module=classifier_module,
        model_provider=model_provider,
    )

    return Container(
        settings=settings,
        cache=cache,
        cache_mode=cache_result.mode,
        policy_repository=policy_repository,
        protection=protection,
        policy_watcher=PolicyFileWatcher(settings.policy_file_path, policy_notifier.reload),
        policy_notifier=policy_notifier,
        call_ids=call_ids,
        signature_watcher=PolicyFileWatcher(settings.signatures_file_path, reload_signatures),
        signature_feed=signature_feed,
        user_repository=user_repository,
        token_verifier=token_verifier,
        model_provider=model_provider,
        model_selection=model_selection,
        model_directory=model_directory,
        gateway_credentials=gateway_credentials,
        mcp_registry=mcp_registry,
        mcp_gateway=mcp_gateway,
        classifier=classifier,
        evaluator_registry=registry,
        stages=stages,
        pipeline=pipeline,
        identity_service=identity_service,
        tool_catalog=tool_catalog,
        audit_repository=audit_repository,
        alert_store=alert_store,
        feed_broadcaster=feed_broadcaster,
        metrics_collector=metrics,
        list_users=ListUsersUseCase(user_repository),
        issue_token=issue_token,
        get_me=GetMeUseCase(
            tool_catalog,
            budget_repository,
            risk_repository,
            policy_repository,
            model_provider,
            protection,
        ),
        list_tools=ListToolsUseCase(tool_catalog),
        chat_completion=chat_completion,
        tool_call=tool_call,
        get_approval=GetApprovalUseCase(approval_service, identity_service),
        execute_approval=execute_approval,
        list_feed=ListFeedUseCase(audit_repository),
        stream_feed=StreamFeedUseCase(feed_broadcaster, stats),
        list_audit=ListAuditUseCase(audit_repository),
        call_detail=GetCallDetailUseCase(audit_repository),
        export_audit=ExportAuditUseCase(audit_repository),
        list_alerts=ListAlertsUseCase(alert_store),
        export_alerts=ExportAlertsUseCase(settings.alerts_xlsx_path),
        stats=stats,
        policy_view=policy_view,
        reload_policy=ReloadPolicyUseCase(policy_repository, policy_view),
        security_report=SecurityReportUseCase(stats, audit_repository, alert_store),
        reset_demo=ResetDemoUseCase(
            audit_repository,
            alert_store,
            budget_repository,
            session_repository,
            risk_repository,
            approval_repository,
            cache,
            metrics,
            clear_logs,
            protection,
        ),
        clear_logs=clear_logs,
        manage_protection=ManageProtectionUseCase(protection, policy_repository),
        health=GetHealthUseCase(),
        attack_runs=attack_runs,
        reset_runtime_state=reset_runtime_state,
        classifier_module=classifier_module,
        workbench=workbench,
    )


async def _seed_call_ids(container: Container) -> None:
    await container.call_ids.seed(await highest_call_id(container.audit_repository))


async def start(container: Container) -> None:
    await _seed_call_ids(container)
    await container.model_selection.restore()
    await container.mcp_registry.start()
    container.policy_watcher.start()
    container.signature_watcher.start()
    await container.policy_watcher.check_once()
    await container.signature_watcher.check_once()


async def stop(container: Container) -> None:
    await container.policy_watcher.stop()
    await container.signature_watcher.stop()
    await container.feed_broadcaster.close()
    await container.mcp_registry.aclose()


async def collect_health(container: Container) -> HealthView:
    status = await container.policy_repository.status()
    classifier_info = container.classifier.info()
    return container.health.execute(
        cache_mode=container.cache_mode,
        mcp_servers=[
            McpServerStatus(
                name=name, status=info["status"], tools=info["tools"], error=info.get("error")
            )
            for name, info in container.mcp_registry.status().items()
        ],
        classifier=ClassifierStatus(
            loaded=bool(classifier_info.get("loaded")), path=classifier_info.get("path")
        ),
        provider=container.model_provider.describe(),
        policy_status=PolicyStatus(version=status["version"] or 0, status=status["status"]),
        protection=await current_protection(container.protection),
        gateway=GatewayInfo(
            default_user=container.gateway_credentials.default_user, ollama_api=True
        ),
    )
