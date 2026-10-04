# AI Control Layer Architecture

## Overview

The AI Control Layer is a policy-enforcing proxy gateway that sits between AI agents and upstream services (language models, MCP tool servers). It implements centralized governance through a seven-stage deterministic and AI-driven processing pipeline, with hot-reloadable policy, real-time audit and alerting, budget enforcement, and OWASP-grounded controls.

## Component Diagram

```mermaid
graph LR
    A["Employee Chat / Attack Suite / Curl"]
    B["Demo Agent Service<br/>:8090"]
    C["AI Control Layer<br/>:8080"]
    D["Ollama<br/>:11434"]
    E["MCP Demo Servers<br/>stdio"]
    F["Redis<br/>:6379"]
    G["Dashboard<br/>:5173"]

    A -->|Bearer JWT| B
    B -->|/v1/chat/completions<br/>Bearer JWT| C
    C -->|OpenAI-compatible| D
    C -->|stdio calls| E
    C -->|cache/state| F
    G -->|Admin API| C
    
    style C fill:#ff6b6b,stroke:#333,color:#fff
    style B fill:#4ecdc4,stroke:#333,color:#fff
    style D fill:#45b7d1,stroke:#333,color:#fff
    style E fill:#95e1d3,stroke:#333,color:#fff
    style F fill:#f38181,stroke:#333,color:#fff
```

## Seven-Stage Processing Pipeline

Every intercepted call (prompt → model, model response, tool call → MCP, tool result) passes through this **fixed, ordered pipeline** with timing and short-circuit capability:

```mermaid
graph TD
    Start["Request"]
    Stage1["1. Identity<br/>Verify JWT<br/>Resolve claims"]
    Stage2["2. Authorization<br/>Role provisioning<br/>Resource scope (paths)<br/>Residency check<br/>Approval gate"]
    Stage3["3. DLP<br/>PII/secrets detection<br/>Exfiltration rules<br/>Sequence rules<br/>Session vault (reversible masking)"]
    Stage4["4. Policy<br/>Injection signatures<br/>Decision tree (sampled judge verification)<br/>ML classifier<br/>LLM judge<br/>Topic restrictions<br/>Custom rules"]
    Stage5["5. Behavior Analytics<br/>Rate limit<br/>Loop guard<br/>Circuit breaker<br/>Risk scoring"]
    Stage6["6. Resource Governance<br/>Token budgets<br/>Cost limits<br/>Timeouts"]
    Stage7["7. Audit & Telemetry<br/>Logging<br/>Alerting<br/>Metrics"]
    End["Decision + Result"]

    Start --> Stage1
    Stage1 -->|401 rejected| Stage7
    Stage1 --> Stage2
    Stage2 -->|403 blocked| Stage7
    Stage2 --> Stage3
    Stage3 -->|masked text| Stage4
    Stage3 -->|403 blocked| Stage7
    Stage4 -->|202 escalated| Stage7
    Stage4 -->|403 blocked| Stage7
    Stage4 --> Stage5
    Stage5 -->|403 quarantined| Stage7
    Stage5 -->|429 rate limited| Stage7
    Stage5 --> Stage6
    Stage6 -->|403 budget exceeded| Stage7
    Stage6 --> Stage7
    Stage7 --> End

    style Stage1 fill:#ffe5e5
    style Stage2 fill:#ffe5e5
    style Stage3 fill:#e5f5ff
    style Stage4 fill:#fff5e5
    style Stage5 fill:#f0e5ff
    style Stage6 fill:#e5ffe5
    style Stage7 fill:#e5e5e5
```

## Tool Call Sequence Diagram

Shows how a tool call flows through the pipeline with all interception points:

```mermaid
sequenceDiagram
    actor U as Agent/Caller
    participant CL as Control Layer
    participant I as Identity
    participant AU as Authorization
    participant DLP as DLP
    participant P as Policy
    participant B as Behavior
    participant R as Resource
    participant A as Audit
    participant MCP as MCP Gateway
    participant Cache as Cache

    U ->>+ CL: POST /v1/tools/call
    CL ->>+ I: Verify JWT
    I -->>- CL: Identity resolved or 401
    
    CL ->>+ AU: Check role/residency/approval
    AU ->>+ Cache: Check decision cache
    Cache -->>- AU: Cache hit or miss
    AU -->>- CL: ALLOWED/BLOCKED/202 ESCALATED
    
    CL ->>+ DLP: Detect secrets in args
    DLP ->>+ Cache: Check cache
    Cache -->>- DLP: Hit or miss
    DLP -->>- CL: Masked args / BLOCKED
    
    CL ->>+ P: Check signatures, ML, rules
    P ->>+ Cache: Check cache
    Cache -->>- P: Hit or miss
    P -->>- CL: ALLOWED/BLOCKED/FLAG
    
    CL ->>+ B: Rate limit, loop guard, risk
    B -->>- CL: ALLOWED/BLOCKED/429
    
    CL ->>+ R: Check budget
    R -->>- CL: ALLOWED/BLOCKED/403
    
    alt if BLOCKED or ESCALATED
        CL ->> A: Log rejection
        CL -->> U: 403 / 202 error
    else if ALLOWED
        CL ->>+ MCP: Execute tool call
        MCP -->>- CL: Result
        
        CL ->> DLP: Check result for PII
        CL ->> P: Check result for injection
        CL ->> B: Record execution
        
        CL ->> A: Log success
        CL -->> U: 200 with result
    end
```

## Ports and Adapters Architecture

The codebase follows **Clean Architecture** with strict dependency flow:

```
presentation/
  ├─ routers (FastAPI, SSE)
  ├─ schemas (Pydantic v2)
  └─ composition_root (DI container, stage registry)
       │
application/
  ├─ pipeline/ (ProcessingPipeline, stages)
  ├─ rules/ (RuleRegistry, evaluators)
  ├─ use_cases/ (ChatCompletion, ToolCall, Approvals, etc.)
  ├─ evaluators/ (RBAC, DLP, Signatures, ML, etc.)
  ├─ detectors/ (pure functions for PII, secrets)
  └─ services (budgets, sessions, risk)
       │
domain/
  ├─ models (Identity, Rule, PolicyDocument, etc.)
  ├─ ports (abstract interfaces)
  └─ exceptions
       │
infrastructure/
  ├─ adapters (concrete implementations)
  ├─ providers (Ollama, Mock, OpenAI-compatible)
  ├─ repositories (Redis, In-memory, YAML, Excel)
  └─ ml/ (Sklearn classifier, feature extraction)
```

**Dependency rule:** Domain imports nothing. Application imports domain only. Infrastructure implements domain ports. Composition root is the sole place adapters meet use cases.

## Interception Points and Caching Strategy

Four points where the pipeline intercepts traffic:

| Point | Trigger | Cache Key | Cacheable Stages |
|-------|---------|-----------|------------------|
| `prompt` | Before model call | `sha256(role\|point\|text_hash)\|policy_v` | DLP, Policy |
| `response` | After model returns | `sha256(role\|point\|text_hash)\|policy_v` | DLP, Policy |
| `tool_call` | Before MCP tool execution | `sha256(role\|point\|tool_args_hash)\|policy_v` | DLP, Policy |
| `tool_result` | After MCP tool returns | `sha256(role\|point\|result_hash)\|policy_v` | DLP, Policy |

**Cache invalidation:** Policy version change (bump on file reload) automatically invalidates all cache entries. Stages 1, 2, 5, 6, 7 always run (uncacheable).

## Hot-Reload Mechanism

```mermaid
graph TD
    A["File: config/policy.yaml"]
    B["PolicyFileWatcher<br/>polls mtime every 1s"]
    C{File changed?}
    D["Validate with Pydantic"]
    E{Valid?}
    F["Swap immutable<br/>PolicyDocument<br/>Increment version"]
    G["Clear decision cache<br/>Log INFO"]
    H["Keep last good<br/>policy<br/>Log ERROR<br/>Emit ALERT"]

    A --> B
    B --> C
    C -->|yes| D
    C -->|no| B
    D --> E
    E -->|yes| F
    E -->|no| H
    F --> G
    G --> B
    H --> B
```

## Alerting & Audit Architecture

```mermaid
graph LR
    Decision["Pipeline Decision"]
    
    Decision -->|Non-ALLOW| Alert["Alert Created"]
    Alert -->|Write| Excel["Excel File<br/>alerts/alerts.xlsx"]
    Alert -->|Write| Store["In-Memory Store"]
    Alert -->|Broadcast| SSE["Server-Sent Events<br/>Live Feed"]
    
    Decision -->|Always| AuditRec["CallRecord"]
    AuditRec -->|Append| JSONL["Audit Log<br/>audit/calls.jsonl"]
    AuditRec -->|Write| AuditStore["In-Memory Repo<br/>Export: CSV/JSONL/XLSX"]
```

**Excel:** Locked at process level, single writer. JSONL is the durable audit log.

## Performance Telemetry

Every call records per-stage timings and per-user metrics:

- **Stage latencies:** p50/p95 per stage (ms)
- **Proxy overhead:** p50/p95 for full pipeline (ms)
- **Upstream latency:** p50/p95 for model/MCP calls (ms)
- **Cache hit ratio:** percentage of cache hits in DLP + Policy
- **Calls per minute:** throughput gauge

## Scalability Notes and Limitations

**Single Process:**
- No multi-processing (Excel not thread-safe; Redis handles concurrency at connection level)
- Uvicorn workers=1; uvicorn-workers or gunicorn for horizontal scaling would require external coordinator for session/approval state

**In-Memory Fallback:**
- Redis unavailable → all state (budgets, sessions, risk, decision cache) reverts to memory
- No persistence; state resets on restart

**ML/Judge:**
- Inference via `asyncio.to_thread` (non-blocking)
- Model inference ~50–200ms on RTX 4070 with Qwen 7B

**MCP Servers:**
- Stdio processes spawned per startup in `lifespan` context
- Concurrent stdio calls serialized per RFC 5246 (safe)
- Tiny demo servers; production MCP would use HTTP adapters for parallelism

**Session Continuity:**
- `session_id` passed by agent; defaults to `Identity.sub` if omitted
- Taint propagation (sequence rules) is per-session; long-lived sessions accumulate state

## Directory Structure

```
Backend/
  pyproject.toml                      (packaging, dependencies)
  config/
    ├─ policy.yaml                   (hot-reloaded, v3 sample)
    ├─ mcp_servers.yaml              (9 demo servers)
    ├─ attack_signatures.yaml         (local feed)
    └─ users.yaml                    (demo SSO users)
  alerts/                             (generated, Excel file)
  audit/                              (generated, JSONL log)
  src/control_layer/
    ├─ domain/                       (models, ports, exceptions)
    ├─ application/
    │  ├─ pipeline/
    │  │  └─ stages/                 (7 stage implementations)
    │  ├─ evaluators/                (rule evaluators)
    │  ├─ detectors/                 (PII, secrets, patterns)
    │  ├─ rules/                     (registry, type inference)
    │  ├─ budgets/
    │  ├─ sessions/
    │  ├─ approvals/
    │  ├─ behavior/
    │  └─ use_cases/                 (chat, tools, admin endpoints)
    ├─ infrastructure/
    │  ├─ providers/                 (Ollama, Mock, OpenAI-compatible)
    │  ├─ repositories/              (Redis, In-memory, YAML, Excel)
    │  ├─ ml/                        (classifier, features)
    │  ├─ mcp_gateway/
    │  ├─ signature_feed/
    │  └─ adapters/
    ├─ presentation/
    │  ├─ main.py                   (FastAPI app, lifespan)
    │  ├─ routers/                  (v1/*, api/*)
    │  ├─ schemas/                  (Pydantic models)
    │  ├─ composition_root.py        (DI container)
    │  └─ errors.py                 (handlers)
    └─ ml/
       ├─ train.py                   (CLI entry for training)
       ├─ features.py                (TF-IDF)
       ├─ classifier.py              (wrapper)
       ├─ dataset/
       │  └─ prompt_injection_dataset.csv
       └─ artifacts/
          └─ prompt_injection_classifier.joblib
  src/demo_agent/
    ├─ main.py                       (FastAPI app)
    ├─ agent_loop.py                 (OpenAI tool-calling loop)
    └─ control_layer_client.py       (HTTP client)
  tests/
    ├─ unit/
    │  ├─ domain/
    │  ├─ application/
    │  ├─ infrastructure/
    │  └─ ml/
    ├─ integration/
    └─ conftest.py

Frontent/
  src/
    ├─ pages/                        (React routes)
    ├─ components/                   (UI components)
    ├─ hooks/                        (TanStack Query, SSE)
    ├─ api/                          (API client)
    ├─ types/                        (TypeScript types)
    └─ test/

demo/mcp/
  ├─ github.py
  ├─ ci.py
  ├─ logs_db.py
  ├─ jira.py
  ├─ hr_db.py
  ├─ calendar.py
  ├─ mail.py
  ├─ payments.py
  ├─ eu_customers.py
  └─ data.py

WIKI/
  ├─ api-contract.md
  ├─ architecture.md               (this file)
  ├─ policy-reference.md
  ├─ owasp-mapping.md
  ├─ judges-quickstart.md
  ├─ demo-script.md
  ├─ README.MD
  └─ reference/
     ├─ task.req
     └─ ui-mockups.html

presentation/
  ├─ slides.html
  ├─ README.md
  └─ slides.pdf                    (generated)

Root:
  ├─ README.md
  ├─ docker-compose.yml
  ├─ .env.example
  ├─ .dockerignore
  ├─ attack_suite.py
  └─ scripts/
     ├─ bootstrap.{ps1,sh}
     ├─ test.{ps1,sh}
     ├─ lint.{ps1,sh}
     ├─ train_ml.{ps1,sh}
     ├─ run_dev.{ps1,sh}
     └─ export_slides.{ps1,sh}
```

---

**See also:** [API Contract](api-contract.md), [Policy Reference](policy-reference.md), [OWASP Mapping](owasp-mapping.md), [Demo Script](demo-script.md)
