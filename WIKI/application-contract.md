# Application-layer contract (Phase 1)

Builds on `Backend/src/control_layer/domain/**` (frozen after Phase 0, additive changes only) and
`application/pipeline/processing_pipeline.py`. Names below are binding for WS1 (stages, services, proxy use
cases), WS1b (admin/reporting use cases, feed events, attack runs), WS2 (adapters), WS3 (evaluators) and WS4
(FastAPI wiring). All classes are constructor-injected with ports only.

## Additive domain changes (WS1)

- `domain/models/user.py::DemoUser(sub, name, initials, role: Role, location, region, agent_id, mcp_servers: list[str])`
- `domain/ports/user_repository.py::UserRepository` — `async list_all() -> list[DemoUser]`, `async get(sub) -> DemoUser | None`
- `domain/ports/event_publisher.py::EventPublisher` — `async publish(event: str, data: dict) -> None`
- `domain/models/decision.py`: no change. `Decision.approval_id` is filled by the tool-call use case.
- `config/policy.yaml`: add rule `{ id: direct_push_to_main, on: tool_call, match: {action: [push_main]}, action: block, owasp: [ASI02, LLM06], severity: high }`
  before `destructive_requires_approval`; scenario `direct_push_to_main` expects `BLOCKED` / `direct_push_to_main`.

## Context conventions (who fills `ProcessingContext`)

The use case builds the context once per interception point:

| field / metadata key | prompt | response | tool_call | tool_result |
|---|---|---|---|---|
| `text` | joined non-system message contents | assistant text | canonical JSON of `{server, tool, arguments}` | tool result text |
| `chat` | request | request | – | – |
| `tool_call` | – | – | request | request |
| `metadata["token"]` | raw bearer token (all points) | | | |
| `metadata["model"]` | requested model | | | |
| `metadata["max_tokens"]` | requested max_tokens or None | | | |
| `metadata["tool_descriptor"]` | – | – | `ToolDescriptor` resolved from `McpGateway.list_tools()` | same |
| `metadata["session_state"]` | `SessionState` loaded from `SessionRepository` (all points) | | | |
| `metadata["upstream_usage"]` | – | `Usage` of the upstream response | – | – |

`ctx.identity` is set by the Identity stage. `ctx.session_id` = `X-Session-Id` header or the token `sub`.

## Stages (`application/pipeline/stages/`, all subclass `BaseStage`)

Common rule loop (`application/rules/rule_runner.py::RuleRunner`): for every `rule` in `policy.rules` with
`rule.enabled and rule.stage == stage and ctx.point in rule.on`, look up `registry.get(rule.type)` and
`await evaluator.evaluate(rule, ctx, policy)`; a matched outcome becomes
`Violation(stage, rule.id, rule.action, rule.severity, rule.owasp, outcome.evidence, outcome.confidence, outcome.reason)`;
a `masked_text` from an outcome is applied to `ctx.masked_text` before the next rule; the stage result action is
`merge_action` of the violation actions (allow when none), `reason` = reason of the highest-precedence violation.
`application/rules/registry.py::EvaluatorRegistry` — `register(rule_type, evaluator)`, `get(rule_type)` (raises
`UnknownEvaluatorError`), `types()`.

1. `IdentityStage(token_verifier, user_repository)` — verifies `metadata["token"]` (`IdentityRejectedError` on
   failure, raised, not returned), builds `Identity` (fields from claims, `session_id = ctx.session_id`), sets
   `ctx.identity`; returns allow. Also exposed as `application/auth/identity_service.py::IdentityService.resolve(token, session_id) -> Identity`
   for routes that do not run the pipeline (`/v1/me`, `/v1/tools`, approvals).
2. `AuthorizationStage(registry)` — rule loop (types `rbac`, `residency`, `model_allowlist`, `tool_match`);
   `require_approval` outcomes short-circuit with that action.
3. `DlpStage(registry)` — rule loop (`detectors`, `sequence`, `canary_token`); masked text accumulates.
4. `PolicyStage(registry)` — rule loop (`signatures`, `ml_classifier`, `llm_judge`, `restricted_topics`,
   `unsafe_output`, `transaction_limit`, other `tool_match`); when an `ml_classifier` outcome is `inconclusive`
   and `rule.params.get("escalate_to")` names an enabled rule, run that rule's evaluator and use its outcome;
   when no escalation target exists an inconclusive outcome becomes a `flag` violation.
5. `BehaviorStage(registry, session_repository)` — rule loop (`rate_limit`, `loop_guard`, `circuit_breaker`,
   `anomaly`); on `tool_result` adds `metadata["tool_descriptor"].tags` to `session_state.tags_seen` and sets
   `tainted=True` when any earlier stage result in this pass carried a violation whose rule type is
   `signatures`/`ml_classifier`/`llm_judge` (the use case passes `metadata["injection_detected"] = True`);
   persists the session state.
6. `ResourceStage(budget_repository)` — prompt: `BudgetUsage` vs `policy.budgets` (`tokens_used >= per_user_tokens`
   or `cost_used_usd >= per_user_cost_usd` → block with reason "Token budget overrun", or flag when
   `on_exceeded == "warn"`; usage ≥ `warn_at_percent` → flag "Budget at {pct}%"); `max_tokens` above
   `max_tokens_per_request` → flag and `metadata["max_tokens"]` capped; tool_call: `params` quota per session
   (`budgets.tool_calls_per_session`, optional, default unlimited).
7. `AuditStage(event_publisher)` — publishes `{"event": "stage_trace", "call_id", "point", "stages": timings}` and
   returns allow; the `CallRecord` itself is written by `AuditService` (below) after the whole call.

## Services (`application/services/`)

- `CallIdGenerator(cache)` — `async next() -> str` (`c_{n:06d}` from `incr("calls:seq")`).
- `BudgetService(budget_repository)` — `async record(identity, usage: Usage, model, policy) -> BudgetUsage`
  (cost from `policy.models.pricing`, 0 when missing).
- `SessionService(session_repository)` — `async load(session_id) -> SessionState`, `async save(state)`.
- `ApprovalService(approval_repository, cache)` — `async create(identity, tool_call, rule_id, reason) -> PendingApproval`
  (`ap_` + 12 hex, expires in 15 min), `async get_for(identity, approval_id) -> PendingApproval` (404-style
  `ApprovalNotFoundError`, forbidden when another user's), `async mark(approval_id, status)`.
- `CircuitBreakerService(cache, alert_sink, policy_repository)` — `async record_block(identity, call_id)`:
  `incr("cb:{sub}")` with the rule's `window_s`; at `blocks` threshold set `quarantine:{sub}` for `window_s` and
  emit a critical alert (rule `circuit_breaker`, reason "User quarantined after repeated blocked actions").
- `RiskService(risk_repository)` — `async record(identity, decision) -> RiskProfile` (score += 10 block, 5
  escalate, 3 mask/flag; level low <25, medium <50, high <75, critical; signals = last 10 rule ids).
- `AlertFactory` — `build(call_record, decision) -> Alert | None` (None for ALLOWED; severity from the primary
  violation; `rule_id` may be None for structural blocks such as budget).
- `AuditService(audit_repository, alert_sink, alert_store, event_publisher, alert_factory, policy_repository)` —
  `async record(call: CallRecord, decision: Decision) -> Alert | None`: appends the record, builds the alert,
  emits it to the sink and store, publishes `feed` (FeedRow dict), `alert` (when any) and `stats_dirty` events.
  `application/audit/call_record_builder.py::CallRecordBuilder` — `build(...)` from identity, kind, target,
  decision(s), request, raw/delivered response, items_masked, usage, latencies, provider, matched rule YAML
  (`application/audit/rule_yaml.py::rule_to_yaml(rule)`).
- `ToolCatalog(mcp_gateway, policy_repository)` — `async provisioned_for(identity) -> list[ToolDescriptor]`
  (servers in `policy.roles[role].mcp_servers`, minus `tools_deny`, minus tools whose `data_region` excludes the
  user's region), `async descriptor(server, tool) -> ToolDescriptor` (`UnknownToolError`).

## Proxy use cases (`application/use_cases/`)

- `IssueTokenUseCase(user_repository, token_verifier, ttl_s=28800).execute(sub) -> TokenIssued(access_token, token_type, expires_in, claims: TokenClaims)`
- `ListUsersUseCase(user_repository).execute() -> list[DemoUser]`
- `GetMeUseCase(tool_catalog, budget_repository, risk_repository, policy_repository, model_provider).execute(identity) -> MeView(identity, tools, policy_name, policy_version, budget: BudgetUsage, risk: RiskProfile, provider: ProviderInfo)`
- `ListToolsUseCase(tool_catalog).execute(identity) -> list[ToolDescriptor]`
- `HandleChatCompletionUseCase(pipeline, identity_service, model_provider, budget_service, session_service, audit_service, circuit_breaker, risk_service, call_ids, policy_repository, canary_token: str)`
  `.execute(token, session_id, request: ChatCompletionRequest) -> ChatCompletionOutcome(call_id, response: ChatCompletionResponse, status, stage, rule_id, reason, items_masked, proxy_latency_ms, upstream_latency_ms)`.
  Flow: call_id → prompt pass (block/quarantine → audit + circuit breaker + raise the mapped error with
  `call_id`; rate_limit violation → `RateLimitedError`; budget → `BudgetExceededError`) → forward the masked
  request (system message gets the canary line appended when a `canary_token` rule is enabled) with
  `max_tokens` capped → provider (`asyncio.wait_for(policy.budgets.upstream_timeout_s)`, `UpstreamProviderError`
  on failure) → response pass on the assistant text → block → audit + raise; mask → replace the assistant text
  → record usage/cost → audit (always, including errors) → outcome. `items_masked` counts placeholders in the
  delivered text. The `stage`/`rule_id`/`reason` come from the primary violation of the combined passes.
- `HandleToolCallUseCase(pipeline, tool_catalog, mcp_gateway, approval_service, session_service, audit_service, circuit_breaker, risk_service, call_ids, policy_repository)`
  `.execute(token, session_id, request: ToolCallRequest) -> ToolCallOutcome(call_id, status, stage, rule_id, reason, items_masked, result: ToolCallResult | None, approval: PendingApproval | None)`.
  Flow: descriptor → tool_call pass → `require_approval` → create approval, audit ESCALATED, return outcome
  with `approval` (router → 202); block → audit + raise; else gateway call → tool_result pass (masked result
  delivered) → audit → outcome.
- `ExecuteApprovalUseCase(...)` — `approve(token, approval_id) -> ToolCallOutcome` (runs the held call through
  `HandleToolCallUseCase` with `metadata["approved"] = True` so `tool_match`/`require_approval` is skipped —
  pass this flag in the request path, the AuthorizationStage honours `ctx.metadata.get("approved")`), marks the
  approval `executed`; `reject(token, approval_id) -> PendingApproval` (status rejected, audited as BLOCKED with
  reason "Rejected by user").
- `GetApprovalUseCase(approval_service).execute(token, approval_id) -> PendingApproval`

Errors carry `call_id` so the router can put it in the error envelope: all `ControlLayerError` subclasses get an
optional `call_id` attribute (additive change to `domain/exceptions.py`).

## Admin use cases (`application/use_cases/admin/`, WS1b)

- `FeedQuery(user, role, status, kind, limit=100)`; `ListFeedUseCase(audit_repository).execute(query) -> list[CallRecord]`
- `ListAuditUseCase(audit_repository).execute(query) -> list[CallRecord]`; `GetCallDetailUseCase(audit_repository).execute(call_id) -> CallRecord` (`CallNotFoundError`)
- `ExportAuditUseCase(audit_repository).execute(fmt: "jsonl"|"csv"|"xlsx") -> ExportFile(filename, media_type, content: bytes)`
- `ListAlertsUseCase(alert_store).execute(limit, user, rule_id) -> list[Alert]`; `ExportAlertsUseCase(alerts_xlsx_path).execute() -> ExportFile`
- `StatsCalculator(audit_repository, budget_repository, risk_repository, metrics_collector, policy_repository, model_provider, user_repository).compute() -> StatsView` (contract `/api/stats`)
- `MetricsCollector` (`application/telemetry/metrics_collector.py`) — `record(call_record)`, `snapshot() -> MetricsView` (p50/p95 per stage, proxy, upstream, cache hits/misses, calls/min), `record_cache(hit: bool)`, `reset()`; the pipeline cache hit flag is taken from `Decision.stage_results[*].cache_hit`.
- `GetPolicyViewUseCase(policy_repository).execute() -> PolicyView(version, status, loaded_at, source, error, raw_yaml, document, rules_by_stage)`; `ReloadPolicyUseCase`
- `SecurityReportUseCase(stats_calculator, audit_repository, alert_store).execute(period) -> ReportView(generated_at, period, summary, top_rules, top_users, owasp_coverage, recommendations, markdown)`
- `ResetDemoUseCase(audit_repository, alert_store, budget_repository, session_repository, risk_repository, approval_repository, cache, metrics_collector).execute()` — clears everything except the policy; flushes cache prefixes `decision:`, `rate:`, `loop:`, `cb:`, `quarantine:`, `seen:`, `calls:`.
- `GetHealthUseCase(...)` → `HealthView` per the contract (`stages`, cache mode, MCP servers, classifier, provider, policy).
- `FeedBroadcaster` (`application/events/feed_broadcaster.py`, implements `EventPublisher`) — `subscribe() -> AsyncIterator[FeedEvent(event, data)]`, per-subscriber bounded queues; `StreamFeedUseCase(broadcaster, stats_calculator)` yields `feed`, `alert` and (on `stats_dirty`, throttled to 1/s) `stats` events.
- Attack suite: `ScenarioClient` Protocol (`application/selftest/scenario_client.py`): `async token_for(sub) -> str`,
  `async tamper(token, claim, value) -> str`, `async expired_token(sub) -> str`, `async chat(token, session_id, message, model=None) -> StepObservation(http_status, status, stage, rule_id, reason, approval_id)`,
  `async tool_call(token, session_id, server, tool, arguments) -> StepObservation`, `async approve(token, approval_id) -> StepObservation`,
  `async agent_chat(token, session_id, prompt) -> list[StepObservation]` (Ollama tier; may raise `AgentUnavailableError`).
  `ScenarioExecutor(client).run(scenario, tier) -> ScenarioResult(id, status, observed, duration_ms, error)` with
  the status rules: negative → STOPPED when observed status/rule match expected (rule match only when expected
  rule_id is not None), SUCCEEDED when the call was ALLOWED/MASKED where a BLOCK/ESCALATE was expected, ERROR on
  exceptions; positive → PASSED when ALLOWED/MASKED as expected, otherwise SUCCEEDED is not used — use ERROR with
  the observation; Ollama tier → NOT_ATTEMPTED when no observation involved the expected tool.
  `AttackRunManager(executor_factory, broadcaster).start(agent) -> AttackRun`, `get(run_id)`, `subscribe(run_id)`,
  runs scenarios sequentially in a background task, publishes `scenario` and `run_complete` events.

## Composition root (WS4)

`presentation/composition_root.py::build_container(settings) -> Container` registers the stages in
`StageName.ordered()` order, wires `build_evaluators(EvaluatorDependencies(...))` into the registry, and exposes
every use case as an attribute. Routers depend on `Container` only.
