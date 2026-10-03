# AI Control Layer

**A policy-enforcing proxy gateway for AI agents**—governance at every interception point, hybrid threat detection (rules + ML + LLM judge), real-time audit, and hot-reloadable policy.

## The Problem

AI agents are powerful but dangerous. They make unsupervised tool calls, leak sensitive data, fall victim to prompt injection, and exceed budgets. Traditional API gateways don't understand LLM semantics. **You need a smart proxy that speaks the language of agents.**

## The Solution

The AI Control Layer sits between your agent and backend services (Ollama, MCP servers). It enforces a **seven-stage processing pipeline**:

1. **Identity** — Verify JWT, resolve user claims (role, location)
2. **Authorization** — Role-based tool provisioning, residency checks, approval gates
3. **DLP** — Detect and mask PII, detect secrets, enforce exfiltration rules
4. **Policy** — Signature-based injection detection, ML classifier, LLM judge
5. **Behavior** — Rate limits, loop guards, circuit breaker, anomaly scoring
6. **Resource** — Token budgets, cost limits, timeouts
7. **Audit** — Logging, alerting (Excel + real-time SSE), exportable reports

Every call flows through all stages in order. Stages can short-circuit (return early). Decisions are cached by role + policy version for speed.

## Features by Pipeline Stage

| Stage | Capabilities |
|-------|------|
| **Identity** | JWT verification (HS256), signature check, expiry validation, tampering detection → 401 |
| **Authorization** | RBAC (roles → tools mapping), data residency, destructive-action approval gates → 403 / 202 |
| **DLP** | PII detection (email, phone, PESEL, IBAN, PAN), secrets (API key, JWT, private key), exfiltration sequences → masked or blocked |
| **Policy** | Signature-based injection (feed-driven), ML classifier (Scikit-learn, F1 ≥0.85), LLM judge (Ollama), restricted topics → 403 or escalate |
| **Behavior** | Rate limit (60/min), loop guard (5 identical), circuit breaker (5 blocks → quarantine), risk scoring → 429/403 or quarantine |
| **Resource** | Per-user token budgets (10k/day), cost limits ($1/day), max tokens/request (2k), upstream timeout (30s) → 403 if exceeded |
| **Audit** | Call logging (JSONL), alerting (Excel + SSE), per-stage timing, raw vs delivered response → always |

## Quickstart

### Prerequisites (Native — Recommended for Live Demo)

- Python 3.13+
- Node 24+
- Ollama (optional; mock fallback included)

### Option 1: Run Natively with Scripts (Recommended)

**Why recommended:** Ollama and MCP servers work without extra network setup. Best for the live demo.

#### 1. Bootstrap (2 min)

```bash
./scripts/bootstrap.sh    # PowerShell: .\scripts\bootstrap.ps1
```

Installs Python deps, Node modules, trains ML classifier, pulls Ollama model.

#### 2. Run Dev Servers (1 min)

```bash
./scripts/run_dev.sh      # PowerShell: .\scripts\run_dev.ps1
```

Starts Control Layer (:8080), Demo Agent (:8090), Dashboard (:5173).

#### 3. Sign In and Chat (2 min)

Open **http://localhost:5173** → sign in as **Anna Kowalska** (Developer, Kraków).

Type: `Why did the login tests fail? Check CI and logs.`

Watch:
1. `ci.get_run` → **ALLOWED** (provisioned)
2. `logs-db.query` → **MASKED** (3 emails masked)
3. `hr-db.find_approver` → **BLOCKED** (not provisioned for Developer)

#### 4. Run Self-Testing Suite (1 min)

```bash
python attack_suite.py --target http://localhost:8080
```

24 scenarios (5 positive, 19 negative) pass → exit 0.

### Option 2: Run with Docker

For containerized deployment, see **[Running with Docker](WIKI/judges-quickstart.md#running-with-docker)** in the Judges Quickstart guide.

**Prerequisites:** Ollama must listen on all interfaces (`OLLAMA_HOST=0.0.0.0:11434`), and Windows Firewall must allow inbound TCP 11434. See the guide for full setup.

## Use it as a gateway (VS Code Copilot, any Ollama or OpenAI client)

The control layer is a drop-in replacement for an Ollama or OpenAI-compatible endpoint. Point a
client at `http://localhost:8080` and every prompt and response runs through the seven-stage
pipeline, is audited and shows up in the admin live feed:

- Ollama-native API at the root: `GET /api/tags`, `POST /api/show`, `POST /api/chat` (NDJSON
  streaming by default), `POST /api/generate`, `GET /api/version`, `GET /api/ps`.
- OpenAI-compatible API: `POST /v1/chat/completions` (now with `stream: true`, SSE) and `GET /v1/models`.
- Credentials: a mock-SSO JWT, one of the demo API keys from `Backend/config/users.yaml`
  (for example `Authorization: Bearer ck-anna-dev-2026`), or no credentials at all, which maps to
  `CTRL_GATEWAY_DEFAULT_USER` (default `anna.kowalska`; empty disables it).
- Verdicts for streaming clients are delivered in-band as an assistant message
  (`[BLOCKED by AI Control Layer] authorization · model_allowlist: ...`), because IDE clients hide
  HTTP error bodies. The audit log and feed still record BLOCKED.

```bash
curl -N http://localhost:8080/api/chat -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"hello"}]}'
```

VS Code: open **Chat: Manage Language Models**, add a custom OpenAI-compatible endpoint with URL
`http://localhost:8080/v1`, API key `ck-anna-dev-2026` and model `qwen2.5:7b` (older builds: set the
Ollama endpoint to `http://localhost:8080`). Full steps, limitations and examples:
**[WIKI/gateway.md](WIKI/gateway.md)**.

## Documentation

- **[Judges Quickstart](WIKI/judges-quickstart.md)** — 10-minute getting-started guide
- **[Demo Script](WIKI/demo-script.md)** — 6-minute presentation walkthrough
- **[Architecture](WIKI/architecture.md)** — System design, Mermaid diagrams, pipeline details
- **[API Contract](WIKI/api-contract.md)** — Endpoints, schemas, authentication
- **[Gateway](WIKI/gateway.md)** — Ollama / OpenAI-compatible surfaces, API keys, VS Code Copilot setup
- **[Policy Reference](WIKI/policy-reference.md)** — Policy.yaml syntax, rule types, examples
- **[OWASP Mapping](WIKI/owasp-mapping.md)** — LLM Top 10 2025 + Agentic Top 10 2026 coverage

## Testing

```bash
# Unit + integration tests
cd Backend
python -m pytest -q --cov=control_layer --cov-report=term-missing

# Linting
./scripts/lint.sh

# Attack suite (scripted tier)
python attack_suite.py --target http://localhost:8080

# Attack suite (Ollama tier: agent-driven scenarios go to the real model and report
# NOT_ATTEMPTED if it never tries them; the 7 deterministic ones run scripted.
# Needs provider ollama and protection enforce; the run header shows both.)
python attack_suite.py --target http://localhost:8080 --agent ollama
```

## Docker Deployment

For full Docker setup instructions, including Ollama network configuration, see **[Running with Docker](WIKI/judges-quickstart.md#running-with-docker)** in the Judges Quickstart guide.

Quick start (after Ollama is configured):

```bash
docker-compose up
```

Services: `control-layer` (:8080), `demo-agent` (:8090), `frontend` (:5173), `redis` (:6379).

## Configuration

Copy `.env.example` to `.env`:

```bash
CTRL_MODEL_PROVIDER=auto
CTRL_OLLAMA_BASE_URL=http://localhost:11434
CTRL_OLLAMA_MODEL=qwen2.5:7b
CTRL_REDIS_URL=redis://localhost:6379/0
CTRL_JWT_SECRET=dev-secret-change-me
CTRL_ADMIN_TOKEN=admin-dev-token
```

See [API Contract](WIKI/api-contract.md#configuration) for full reference.

## Performance

On RTX 4070 (Ollama qwen2.5:7b):

- **Proxy overhead:** p50 ~3ms, p95 ~10ms (pipeline stages)
- **Upstream latency:** p50 ~640ms, p95 ~2100ms (Ollama completions)
- **Cache hit ratio:** ~37% (DLP + Policy decision cache)
- **ML inference:** ~50–200ms per classification
- **Throughput:** ~12 calls/min per user (rate limit)

## Architecture

```
Employee Chat / Attack Suite
    ↓ Bearer JWT
Demo Agent Service (:8090)
    ↓
AI Control Layer (:8080)
    ├─ Seven-stage pipeline (Identity → Audit)
    ├─ Decision cache (Redis or in-memory)
    └─ Providers: Ollama / Mock / OpenAI-compatible
    ├─→ Ollama (:11434, qwen2.5:7b)
    ├─→ MCP Servers (9 demo servers: GitHub, CI, Logs, HR, Finance, etc.)
    └─→ Redis (:6379, optional)

Dashboard (:5173)
    └─ Sign-in, Chat, Live Feed, Audit, Policy, Attack Suite
```

## Key Concepts

### Hot-Reloadable Policy

Edit `Backend/config/policy.yaml`. Within 1 second:
- File watcher detects change
- Policy validates via Pydantic
- If valid: version bumps, decision cache clears, new policy active
- If invalid: keeps last good policy, emits alert

No restart needed.

### Three-Tier Defense

1. **Signatures** — Regex patterns (fast, zero false positives)
2. **ML Classifier** — Scikit-learn TF-IDF (detects subtle attacks, F1 ≥0.85)
3. **LLM Judge** — Ollama for edge cases (context-aware, 20s timeout → flag)

### OWASP Coverage

- **LLM Top 10 2025:** All 10 threats covered (except LLM08 out-of-scope, LLM09 partial)
- **Agentic Top 10 2026:** All 10 threats covered (except ASI07 out-of-scope)
- See [OWASP Mapping](WIKI/owasp-mapping.md) for threat-by-threat proof

## Troubleshooting

### Ollama not available?
Control layer auto-fallbacks to `MockModelProvider`. Demo works; scripted tests pass.

### Redis down?
Auto-fallback to in-memory. State resets on restart.

### Tests failing?
```bash
python -m pytest -vv tests/unit/application/
```

See [Judges Quickstart](WIKI/judges-quickstart.md#troubleshooting).

## License

Apache License 2.0. See `LICENSE` file.

## Submission

**Team:** SecCodeSmith (WS6b + Core Streams)  
**Challenge:** HackYeah 2026  
**Deadline:** 2026-10-04 23:00

---

Start here: [Judges Quickstart](WIKI/judges-quickstart.md) (10 min) or [Demo Script](WIKI/demo-script.md) (6 min presentation).