# API contract (v1) — the integration source of truth

All streams build against this document. Changes are additive only after Phase 0.

## Services and ports

| Service | Base URL | Package |
|---|---|---|
| AI Control Layer | `http://localhost:8080` | `Backend/src/control_layer` |
| Demo agent service | `http://localhost:8090` | `Backend/src/demo_agent` |
| Dashboard (Vite) | `http://localhost:5173` | `Frontent/` |
| Ollama | `http://localhost:11434` | external |
| Redis (optional) | `redis://localhost:6379/0` | external |

## Enumerations

- `status` (call outcome): `ALLOWED` | `MASKED` | `BLOCKED` | `ESCALATED` | `FLAGGED`
- `stage`: `identity` | `authorization` | `dlp` | `policy` | `behavior` | `resource` | `audit` (fixed order)
- `point` (interception point): `prompt` | `response` | `tool_call` | `tool_result`
- `rule action` (policy.yaml): `allow` | `flag` | `mask` | `block` | `require_approval` | `quarantine`
- `role`: `developer` | `hr` | `finance`
- `approval status`: `pending` | `approved` | `rejected` | `executed` | `expired`
- `scenario status` (attack suite): `PENDING` | `RUNNING` | `STOPPED` | `PASSED` | `SUCCEEDED` | `NOT_ATTEMPTED` | `ERROR`
  (`STOPPED` = attack was blocked/masked/escalated as expected; `PASSED` = positive case allowed as expected;
  `SUCCEEDED` = attack got through, suite fails; `NOT_ATTEMPTED` = Ollama tier only, model never tried the risky call)
- `provider`: `ollama` | `mock` | `openai_compatible`

Qualified tool name: `"<server>.<tool>"`, server ids use hyphens as in policy.yaml (`logs-db.query`,
`hr-db.find_approver`, `github.delete_branch`). Chat completions appear in feeds as target `llm.complete`.

## Authentication

- Proxy and user endpoints (`/v1/*`): `Authorization: Bearer <jwt>`. JWT is HS256 signed with `CTRL_JWT_SECRET`,
  claims `{sub, name, role, location, region, agent_id, iss: "control-layer-mock-sso", iat, exp}`.
  Tampering the payload (for example changing `role`) invalidates the signature → 401 `identity_rejected`.
- Admin endpoints (`/api/*`): header `X-Admin-Token: <token>` (`CTRL_ADMIN_TOKEN`, dev default `admin-dev-token`).
- Optional header on `/v1/*`: `X-Session-Id` (conversation id for sequence rules and loop guard; defaults to the token `sub`).

## Error shape (every non-2xx JSON response)

```json
{"error": {"code": "policy_violation", "status": "BLOCKED", "stage": "authorization", "rule_id": "role_provisioning",
           "reason": "HR database is not provisioned for the Developer role", "owasp": ["ASI03", "LLM06"],
           "call_id": "c_000139"}}
```

| HTTP | code | stage |
|---|---|---|
| 401 | `identity_rejected` | identity |
| 403 | `policy_violation` | authorization / dlp / policy |
| 403 | `quarantined` | behavior |
| 429 | `rate_limited` | behavior |
| 403 | `budget_exceeded` | resource |
| 400 | `streaming_not_supported` | - |
| 422 | `validation_error` | - |
| 502 | `upstream_error` | - |

## Control layer — auth and identity

`GET /auth/users` → `{"users": [{"sub": "anna.kowalska", "name": "Anna Kowalska", "initials": "AK", "role": "developer",
"location": "Krakow, PL", "region": "PL", "mcp_servers": ["github", "ci", "logs-db", "jira"]}]}`

`POST /auth/token` body `{"sub": "anna.kowalska"}` → `{"access_token": "...", "token_type": "Bearer", "expires_in": 28800,
"claims": {...}}`

`GET /v1/me` →

```json
{"identity": {"sub": "anna.kowalska", "name": "Anna Kowalska", "role": "developer", "location": "Krakow, PL", "region": "PL", "agent_id": "agent-anna-dev-7f3a"},
 "tools": ["ToolDescriptor"],
 "policy": {"name": "roles.developer", "version": 3},
 "budget": {"tokens_used": 3420, "tokens_limit": 10000, "cost_used_usd": 0.0012, "cost_limit_usd": 1.0, "resets_at": "2026-10-05T00:00:00Z"},
 "risk": {"score": 12, "level": "low"},
 "provider": {"name": "ollama", "model": "qwen2.5:7b"}}
```

`ToolDescriptor` = `{"server": "github", "name": "delete_branch", "qualified_name": "github.delete_branch",
"description": "...", "input_schema": {"...": "JSON schema"}, "tags": ["destructive"], "data_region": null, "scope": "read+write"}`

## Control layer — proxy

`POST /v1/chat/completions` — OpenAI request shape (`model`, `messages[{role, content}]`, optional `tools`,
`tool_choice`, `temperature`, `max_tokens`, `response_format`; `stream: true` → 400). Response is the OpenAI
shape (`id`, `object`, `created`, `model`, `choices[{index, message{role, content, tool_calls?}, finish_reason}]`,
`usage{prompt_tokens, completion_tokens, total_tokens}`) plus an extension object:

```json
"control_layer": {"call_id": "c_000140", "status": "MASKED", "stage": "dlp", "rule_id": "pii_masking",
                  "reason": "3 email addresses masked in the response", "items_masked": 3,
                  "proxy_latency_ms": 4.2, "upstream_latency_ms": 812.0}
```

`status` is `ALLOWED` with `stage`/`rule_id` null when nothing matched. Blocked prompts or responses → 403 error shape.

`GET /v1/tools` → `{"tools": ["ToolDescriptor"]}` (only tools provisioned for the caller's role and region).

`POST /v1/tools/call` body `{"server": "logs-db", "tool": "query", "arguments": {"service": "auth", "since": "24h"}, "session_id": "s-1"}`

- 200 → `{"call_id": "c_000139", "status": "MASKED", "stage": "dlp", "rule_id": "pii_masking", "reason": "3 email addresses masked",
  "items_masked": 3, "result": {"content_text": "...", "structured_content": {"...": "..."}, "is_error": false}}`
  (`status` `ALLOWED` when untouched; `structured_content` may be null)
- 202 → `{"call_id": "c_000141", "status": "ESCALATED", "stage": "authorization", "rule_id": "destructive_requires_approval",
  "reason": "Destructive actions need your confirmation", "approval": {"id": "ap_01H...", "expires_at": "..."}}`
- 403/429 → error shape

`GET /v1/approvals/{id}` → `{"id", "status", "tool": "github.delete_branch", "arguments": {}, "rule_id", "reason", "created_at", "expires_at"}`
`POST /v1/approvals/{id}/approve` → 200 same body as a successful tool call (the held call executes once)
`POST /v1/approvals/{id}/reject` → `{"id": "...", "status": "rejected"}`

## Demo agent service

`POST /agent/chat` (Bearer forwarded unchanged) body `{"session_id": "s-1", "message": "Why did the login tests fail last night?"}` →

```json
{"session_id": "s-1",
 "events": [
   {"type": "tool_call", "call_id": "c_1", "tool": "ci.get_run", "arguments": {"pipeline": "e2e-login", "date": "2026-10-02"},
    "status": "ALLOWED", "stage": null, "rule_id": null, "reason": "Matches roles.developer", "items_masked": 0, "result_preview": "..."},
   {"type": "tool_call", "call_id": "c_2", "tool": "logs-db.query", "arguments": {"service": "auth", "since": "24h"}, "status": "MASKED", "stage": "dlp",
    "rule_id": "pii_masking", "reason": "3 email addresses masked in the response", "items_masked": 3, "result_preview": "401 invalid_token user=[EMAIL_1]"},
   {"type": "tool_call", "call_id": "c_3", "tool": "hr-db.find_approver", "arguments": {"request": "test-accounts"}, "status": "BLOCKED", "stage": "authorization",
    "rule_id": "role_provisioning", "reason": "HR database is not provisioned for the Developer role", "items_masked": 0, "result_preview": null},
   {"type": "approval_required", "approval_id": "ap_01H...", "tool": "github.delete_branch", "arguments": {"repo": "web-app", "branch": "feature/old-login"},
    "rule_id": "destructive_requires_approval", "reason": "Destructive actions need your confirmation"},
   {"type": "assistant_text", "text": "The e2e-login run failed because ..."}
 ],
 "budget": {"tokens_used": 3420, "tokens_limit": 10000}}
```

`POST /agent/approvals/{id}` body `{"session_id": "s-1", "decision": "approve"}` (or `"reject"`) → same response shape (events after resuming).
`GET /agent/health` → `{"status": "ok", "control_layer": "http://localhost:8080", "provider": {"name": "ollama", "model": "qwen2.5:7b"}}`

## Control layer — admin (`X-Admin-Token`)

`GET /api/feed?user=&role=&status=&limit=100` → `{"items": ["FeedRow"]}`
`FeedRow` = `{"call_id", "time": "2026-10-03T10:41:40Z", "user": {"sub", "name", "role"}, "kind": "tool_call" | "chat",
"target": "github.delete_branch" | "llm.complete", "status", "stage", "rule_id", "reason"}`
`GET /api/feed/stream` — SSE, events: `feed` (FeedRow), `alert` (Alert), `stats` (Stats snapshot).

`GET /api/audit?limit=&user=&status=&kind=` → `{"items": ["FeedRow + tokens, cost_usd, proxy_latency_ms"]}`
`GET /api/audit/{call_id}` →

```json
{"call_id": "c_000139", "timestamp": "2026-10-03T10:41:40Z", "identity": {"sub": "anna.kowalska", "name": "Anna Kowalska", "role": "developer", "location": "Krakow, PL", "region": "PL", "agent_id": "agent-anna-dev-7f3a"},
 "kind": "tool_call", "target": "logs-db.query", "mcp_server": "logs-db",
 "decision": {"status": "MASKED", "stage": "dlp", "rule_id": "pii_masking", "reason": "3 email addresses masked", "owasp": ["LLM02"]},
 "matched_rule_yaml": "- id: pii_masking\n  on: response\n  detect: [email, phone, pesel, iban]\n  action: mask\n",
 "request": {"summary": "tool: logs-db.query\nparams: service=auth, since=24h\nagent: agent-anna-dev-7f3a", "payload": {"service": "auth", "since": "24h"}},
 "response": {"raw": "02:11:04 401 invalid_token user=t.lis@example.com", "delivered": "02:11:04 401 invalid_token user=[EMAIL_1]"},
 "items_masked": 3, "tokens": {"prompt": 0, "completion": 0, "total": 0}, "cost_usd": 0.0,
 "latency": {"proxy_ms": 4.2, "upstream_ms": 31.0, "stages": {"identity": 0.1, "authorization": 0.2, "dlp": 1.1, "policy": 2.0, "behavior": 0.3, "resource": 0.2, "audit": 0.3}},
 "provider": {"name": "ollama", "model": "qwen2.5:7b"}}
```

`GET /api/audit/export?format=jsonl|csv|xlsx` → file download.

`GET /api/alerts?limit=&user=&rule_id=` → `{"items": ["Alert"]}`;
`Alert` = `{"id", "created_at", "call_id", "user": {"sub", "name", "role"}, "status", "stage", "rule_id", "severity", "owasp": [], "reason", "evidence"}`
`GET /api/alerts/export` → `alerts.xlsx` download.

`GET /api/stats` →

```json
{"total_calls": 148, "allowed": 112, "blocked": 21, "masked": 11, "escalated": 4, "flagged": 0,
 "by_stage": {"dlp": 11, "authorization": 18}, "by_rule": {"pii_masking": 11}, "by_owasp": {"LLM02": 11}, "by_role": {"developer": 90},
 "budget": {"users": [{"sub": "anna.kowalska", "name": "Anna Kowalska", "tokens_used": 3420, "tokens_limit": 10000, "cost_used_usd": 0.001}]},
 "risk": [{"sub": "anna.kowalska", "name": "Anna Kowalska", "score": 12, "level": "low"}], "posture_score": 92, "cache_hit_ratio": 0.37,
 "latency": {"proxy_p50_ms": 3.1, "proxy_p95_ms": 9.8, "upstream_p50_ms": 640, "upstream_p95_ms": 2100},
 "provider": {"name": "ollama", "model": "qwen2.5:7b"}, "policy": {"version": 3, "status": "LOADED"}}
```

`GET /api/metrics` → `{"stages": {"dlp": {"p50_ms": 1.0, "p95_ms": 3.0, "count": 148}}, "proxy": {"p50_ms": 3.1, "p95_ms": 9.8}, "upstream": {"p50_ms": 640, "p95_ms": 2100}, "cache": {"hits": 55, "misses": 93, "hit_ratio": 0.37}, "calls_per_minute": 12.0}`
`GET /metrics` → Prometheus text (P1).

`GET /api/policy` → `{"version": 3, "status": "LOADED" | "ERROR", "loaded_at": "...", "source": "config/policy.yaml", "error": null,
"raw_yaml": "...", "document": {"...": "parsed"}, "rules_by_stage": {"identity": [], "authorization": ["Rule"], "dlp": ["Rule"], "policy": ["Rule"], "behavior": ["Rule"], "resource": [], "audit": []}}`
`POST /api/policy/reload` → same body.

`GET /api/reports/security?period=24h` → `{"generated_at", "period", "summary": {"...": "stats subset"}, "top_rules": [], "top_users": [],
"owasp_coverage": [{"id", "title", "events", "status"}], "recommendations": [], "markdown": "# Security report ..."}`

`GET /api/attack-suite/scenarios` → `{"scenarios": ["Scenario"]}`;
`Scenario` = `{"id": "dev_reads_hr_db", "name": "Developer reads HR database", "kind": "negative" | "positive", "actor": "anna.kowalska",
"stage": "authorization", "expected": {"status": "BLOCKED", "rule_id": "role_provisioning"}, "owasp": ["ASI03"]}`
`POST /api/attack-suite/run?agent=scripted|ollama` → `{"run_id": "run_3", "number": 3, "agent": "scripted", "started_at": "...",
"scenarios": ["Scenario + status PENDING, observed null, duration_ms null"]}`
`GET /api/attack-suite/runs/{run_id}` → same with live statuses and `{"summary": {"stopped", "passed", "succeeded", "not_attempted", "running", "pending"}}`
`GET /api/attack-suite/runs/{run_id}/stream` — SSE events `scenario` (`{"id", "status", "observed": {"status", "stage", "rule_id"}, "duration_ms"}`) and `run_complete` (summary).

`POST /api/demo/reset` → `{"ok": true}` (clears feed, audit, alerts, budgets, sessions, approvals, risk, counters; keeps policy).

`GET /health` (no auth) → `{"status": "ok", "stages": ["identity", "authorization", "dlp", "policy", "behavior", "resource", "audit"],
"cache": {"mode": "redis" | "memory"}, "mcp": {"servers": [{"name": "github", "status": "connected", "tools": 4}]},
"classifier": {"loaded": true, "path": "..."}, "provider": {"name": "ollama", "model": "qwen2.5:7b"}, "policy": {"version": 3, "status": "LOADED"}}`

## Configuration (environment, prefix `CTRL_`)

| Variable | Default | Meaning |
|---|---|---|
| `CTRL_MODEL_PROVIDER` | `auto` | `auto` (Ollama if model present, else mock), `mock`, `openai_compatible` |
| `CTRL_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `CTRL_OLLAMA_MODEL` | `qwen2.5:7b` | model for agent completions |
| `CTRL_JUDGE_MODEL` | same as above | LLM judge model |
| `CTRL_OPENAI_BASE_URL` / `CTRL_OPENAI_API_KEY` | - | explicit OpenAI-compatible endpoint |
| `CTRL_REDIS_URL` | `redis://localhost:6379/0` | falls back to memory when unreachable |
| `CTRL_POLICY_FILE` | `config/policy.yaml` | hot-reloaded |
| `CTRL_MCP_SERVERS_FILE` | `config/mcp_servers.yaml` | |
| `CTRL_SIGNATURES_FILE` | `config/attack_signatures.yaml` | local feed |
| `CTRL_SIGNATURE_FEED_URL` | - | optional HTTP feed (P1) |
| `CTRL_USERS_FILE` | `config/users.yaml` | mock SSO users |
| `CTRL_ALERTS_XLSX` | `alerts/alerts.xlsx` | |
| `CTRL_AUDIT_JSONL` | `audit/calls.jsonl` | |
| `CTRL_ML_MODEL_PATH` | `src/control_layer/ml/artifacts/prompt_injection_classifier.joblib` | |
| `CTRL_JWT_SECRET` | `dev-secret-change-me` | |
| `CTRL_ADMIN_TOKEN` | `admin-dev-token` | |
| `CTRL_CORS_ORIGINS` | `http://localhost:5173` | |
| `CTRL_PORT` | `8080` | |
| `AGENT_CONTROL_LAYER_URL` | `http://localhost:8080` | demo agent → control layer |
| `AGENT_PORT` | `8090` | |
| `VITE_CONTROL_LAYER_URL` / `VITE_AGENT_URL` / `VITE_ADMIN_TOKEN` | `http://localhost:8080` / `http://localhost:8090` / `admin-dev-token` | dashboard |

Paths are relative to `Backend/` (the control layer's working directory).

## Demo users (`config/users.yaml`)

| sub | name | role | location | region | servers |
|---|---|---|---|---|---|
| anna.kowalska | Anna Kowalska | developer | Krakow, PL | PL | github, ci, logs-db, jira |
| marek.nowak | Marek Nowak | hr | Warsaw, PL | PL | hr-db, calendar, mail |
| john.smith | John Smith | developer | New York, US | US | github, ci, logs-db, jira |
| ewa.zielinska | Ewa Zielinska | finance | Warsaw, PL | PL | payments, calendar |

## MCP demo servers and tools (`config/mcp_servers.yaml`)

| server | tools | tags |
|---|---|---|
| github | list_branches, get_readme, delete_branch, push_main | get_readme: read_external; delete_branch, push_main: destructive |
| ci | get_run, list_pipelines | - |
| logs-db | query | - (results contain emails) |
| jira | search | - |
| hr-db | find_approver, get_employee, query | - (results contain PESEL) |
| calendar | list | - |
| mail | send | send_external |
| payments | get_balance, transfer | transfer: destructive, financial |
| eu-customers | read | data_region: eu_customers |

`mcp_servers.yaml` shape:

```yaml
servers:
  - name: github
    transport: stdio
    command: python
    args: ["-m", "demo.mcp.github"]
    cwd: ".."                      # relative to Backend/: the repo root
    env: {PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8"}
    tools:
      get_readme: {tags: [read_external]}
      delete_branch: {tags: [destructive]}
      push_main: {tags: [destructive]}
  - name: eu-customers
    transport: stdio
    command: python
    args: ["-m", "demo.mcp.eu_customers"]
    cwd: ".."
    tools:
      read: {tags: [], data_region: eu_customers}
```

## Addendum (Phase 1)

- Admin SSE endpoints (`/api/feed/stream`, `/api/attack-suite/runs/{id}/stream`) and admin download links
  (`/api/audit/export`, `/api/alerts/export`) also accept the admin token as the query parameter
  `admin_token=<token>`, because browsers cannot set headers on `EventSource` connections or plain links.
- Demo agent events: additive event `{"type": "notice", "status", "stage", "rule_id", "reason"}` for a denied
  chat completion or an exhausted iteration cap; `assistant_text` events may carry `status`, `stage`,
  `rule_id`, `reason` from the completion's `control_layer` extension.
- `ToolDescriptor.scope` is `"write"` when the tool carries the `destructive` tag, else `"read"`.
- `policy.yaml` has 14 rules: `direct_push_to_main` (block) precedes `destructive_requires_approval`.
- `POST /api/demo/reset?scope=behavior` (additive) clears only runtime state (rate limits, loop guard, circuit breaker, quarantine, budgets, sessions, risk, approvals) and keeps audit and alerts; the default `scope=all` is unchanged. The attack suite calls it before every scenario so scenarios do not influence each other.
- `GET /v1/tools?scope=provisioned|all` (default `provisioned`): `scope=all` also lists tools the caller's role is not provisioned for; every item in `tools` carries `provisioned: bool` (additive). Calling an unprovisioned tool still returns 403 `role_provisioning`.

## Addendum (protection, models, logs)

Admin token required on every route below. Full semantics: `WIKI/feature-protection-models-logs.md`.

- `GET /api/protection` and `PUT /api/protection` (body `{"mode": "enforce|monitor|off"}`) return `{"mode", "rule_overrides": {rule_id: bool}, "disabled_rules": [rule_id]}`; an invalid mode is a 422 `validation_error`. Changing the mode flushes the `decision:` cache prefix.
- `PATCH /api/policy/rules/{rule_id}` (body `{"enabled": bool}`) returns `{"rule_id", "enabled", "overridden": true}`; unknown rule id is a 404 `not_found` envelope.
- `DELETE /api/protection/overrides` clears the rule overrides (the mode is kept) and returns the `GET /api/protection` body.
- `GET /api/policy` rules gain `enabled` (effective, override applied) and `overridden: bool`.
- `GET /api/stats`, `GET /health`, `GET /v1/me` and the `stats` SSE event gain `protection: {"mode": "enforce|monitor|off"}`.
- `monitor` downgrades block, quarantine, require_approval and mask results to `flag` (violation `rule_id`/`stage` kept, reason prefixed `[monitor] `, status FLAGGED); `off` runs only the identity and audit stages (status ALLOWED, identity errors still return 401).
- `GET /api/models` returns `{"active": {"name", "model"}, "available": [{"provider", "model", "allowed", "size_gb"}]}`; `allowed` is membership in `policy.models.allowed`, Ollama models come from `GET {ollama_base_url}/api/tags` (none when unreachable), `mock` is always listed.
- `PUT /api/models` (body `{"provider", "model"}`) switches the model for every following call (agents, LLM judge, `/v1/me`, `/health`, `/api/stats`) and returns the new `active` object; a model not in `available` is a 404 `not_found` envelope. The choice is stored under cache key `models:active` and restored at startup when still listed.
- `POST /api/logs/clear` returns `{"ok": true, "cleared": ["audit", "alerts", "alerts_xlsx", "audit_jsonl", "metrics", "feed"]}`; empties the audit log (memory and `calls.jsonl`), the alert store and `alerts.xlsx`, resets metrics and the call id sequence. Budgets, sessions, approvals, risk, protection mode and overrides are kept.
- `POST /api/demo/reset` (scope `all`) additionally resets the protection mode to `enforce` and clears the rule overrides, and clears logs through the same use case.
