# Feature contract: protection switch, model selector, log clearing

Additive to `WIKI/api-contract.md` and `WIKI/application-contract.md`. Binding for the backend and the dashboard.

## Protection mode and rule overrides

- `ProtectionMode` (domain enum): `enforce` (default) | `monitor` | `off`.
  - `enforce`: current behaviour.
  - `monitor`: the pipeline runs every stage and records violations, but every stage result action of
    `block`, `quarantine`, `require_approval` or `mask` is downgraded to `flag` (reason prefixed with
    `[monitor] `), so calls proceed unmasked and the feed shows them FLAGGED with the rule that would have fired.
  - `off`: only the `identity` and `audit` stages run; everything else is skipped; calls are ALLOWED.
- Rule overrides: a runtime map `{rule_id: enabled}` applied on top of the loaded policy document. The file on
  disk stays read-only. Changing the mode or an override flushes the `decision:` cache prefix.
- State lives in the cache under `protection:mode` and `protection:rule_overrides` (JSON), so it survives
  restarts with Redis and resets with `POST /api/demo/reset` (full scope) or `DELETE /api/protection/overrides`.
- Implementation: `application/services/protection_service.py::ProtectionService(cache)` with
  `get_mode() / set_mode(mode) / get_rule_overrides() / set_rule_override(rule_id, enabled) / clear_overrides()`
  (all async, flushing `decision:` on every write). `application/policy/overridden_policy_repository.py::
  OverriddenPolicyRepository(inner, protection_service)` implements `PolicyRepository` and returns the inner
  document with `enabled` replaced per override (`status()` adds `overrides: {rule_id: enabled}`).
  `ProcessingPipeline.__init__` gains `protection: ProtectionService | None = None`; `run()` reads the mode once
  per call and applies the `monitor` / `off` semantics above. Unit tests cover all three modes and the flush.

### Endpoints (admin token)

- `GET /api/protection` → `{"mode": "enforce", "rule_overrides": {"pii_masking": false}, "disabled_rules": ["pii_masking"]}`
- `PUT /api/protection` body `{"mode": "monitor"}` → same body as GET.
- `PATCH /api/policy/rules/{rule_id}` body `{"enabled": false}` → `{"rule_id", "enabled", "overridden": true}`; 404 for unknown rule ids.
- `DELETE /api/protection/overrides` → GET body with an empty map.
- `GET /api/policy` rules gain `enabled` (effective) and `overridden: bool`; `GET /api/stats`, `GET /health` and
  `GET /v1/me` gain `protection: {"mode": "..."}`; the `stats` SSE event carries it too.

## Model selector

- `GET /api/models` → `{"active": {"name": "ollama", "model": "qwen2.5:7b"}, "available": [{"provider": "ollama", "model": "qwen2.5:7b", "allowed": true, "size_gb": 4.7}, {"provider": "ollama", "model": "gemma4:latest", "allowed": false, "size_gb": 6.6}, {"provider": "mock", "model": "mock", "allowed": true, "size_gb": null}]}`
  `allowed` = the model is in `policy.models.allowed`. Ollama models come from `GET {ollama_base_url}/api/tags`
  (empty list when unreachable); `mock` is always present.
- `PUT /api/models` body `{"provider": "ollama", "model": "gemma4:latest"}` → the `active` object. 404 when
  the model is not available; the switch takes effect for every following call, including the LLM judge.
  Choosing a model that is not allowlisted is permitted (the `model_allowlist` rule will then block prompts
  until the policy allows it; the dashboard shows the warning).
- Implementation: `infrastructure/providers/switchable_provider.py::SwitchableModelProvider` implementing
  `ModelProvider` (`complete`/`describe` delegate; `switch(provider)`); the composition root wraps the
  factory result once and injects the wrapper everywhere. `domain/ports/model_directory.py::ModelDirectory`
  (`async list_models() -> list[ModelInfo(provider, model, size_gb)]`) implemented by
  `infrastructure/providers/ollama_model_directory.py` (Ollama tags + mock). `application/services/
  model_selection_service.py::ModelSelectionService(switchable, directory, provider_factory, policy_repository)`
  with `list_models()` and `select(provider, model)`; the selection is stored under cache key
  `models:active` and restored at startup when still available.

## Log clearing

- `POST /api/logs/clear` → `{"ok": true, "cleared": ["audit", "alerts", "alerts_xlsx", "audit_jsonl", "metrics", "feed"]}`.
  Clears the audit repository and truncates `audit/calls.jsonl`, clears the alert store and deletes
  `alerts/alerts.xlsx` (recreated with a header on the next alert), resets the metrics collector and the call-id
  sequence to the highest remaining id (0). Budgets, sessions, approvals, risk, protection mode and overrides
  are untouched (that is `POST /api/demo/reset`'s job, which now also calls the log clearing).
- Implementation: `AlertSink` port gains `async clear()` (Excel sink deletes the file; composite fans out;
  in-memory store already has it); `AuditRepository.clear()` must truncate the JSONL file; new
  `ClearLogsUseCase` in `application/use_cases/admin/clear_logs.py`.

## Dashboard

- Admin header (every admin page): a three-state protection control (Enforce / Monitor / Off) with a
  confirmation dialog before `off`, colour-coded (green / amber / red) and reflected in a badge; a model
  selector dropdown listing `available` models with the `allowed` badge and a warning when the chosen model is
  not allowlisted; the existing "Reset demo" button plus a new "Clear logs" button (`POST /api/logs/clear`).
- Policy page: a toggle per rule (`PATCH /api/policy/rules/{id}`), an "overridden" badge, and a "Clear
  overrides" button; the page header shows the current protection mode.
- Chat header: shows the active model (already) and a small "monitoring only" / "protection off" banner when the
  mode is not `enforce` (from `/v1/me`).
