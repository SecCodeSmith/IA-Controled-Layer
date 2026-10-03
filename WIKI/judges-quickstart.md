# Judges Quickstart Guide

This guide is for hackathon judges to evaluate the AI Control Layer in 10 minutes.

## Prerequisites

- **OS:** Windows 11 (scripts provided) or Linux/macOS (bash variants)
- **Python:** 3.13+
- **Node:** 24+
- **Ollama:** 0.35+ (optional; mock provider fallback included)
- **Disk:** ~5 GB (Ollama model)
- **RAM:** 8 GB (VRAM for Ollama)

Installation:
- Python 3.13: https://www.python.org/downloads/
- Node 24: https://nodejs.org/
- Ollama: https://ollama.com/

## 1. Bootstrap (2 minutes)

```powershell
# PowerShell (Windows)
cd C:\Users\Kuba\Documents\IA-Controled-Layer
.\scripts\bootstrap.ps1
```

```bash
# Bash (Linux/macOS)
cd ~/IA-Controled-Layer
./scripts/bootstrap.sh
```

**What happens:**
- Backend Python deps installed
- Frontend Node modules installed
- ML classifier trained (F1 ≥0.85)
- Ollama model pulled (qwen2.5:7b, ~4.7 GB) in background
- Warm-up completion sent to Ollama

**Expected output:**
```
=== AI Control Layer Bootstrap ===
  ✓ Backend dependencies installed
  ✓ Frontend dependencies installed
  ✓ ML classifier trained
  ✓ Ollama model pulled
  ✓ Ollama warm-up completed
```

If Ollama isn't installed, the script skips it and the control layer uses mock provider (still demos policy enforcement).

## 2. Run Development Servers (2 minutes)

```powershell
.\scripts\run_dev.ps1
```

```bash
./scripts/run_dev.sh
```

**Expected output:**
```
=== AI Control Layer Development Servers ===
  ✓ Control Layer PID: 12345
  ✓ Demo Agent PID: 12346
  ✓ Frontend running in new window

=== Running Services ===
  Control Layer: http://localhost:8080/health
  Demo Agent:    http://localhost:8090/agent/health
  Dashboard:     http://localhost:5173

Press Ctrl+C to stop all services...
```

Open three browser tabs:

1. **Health checks (verify all running):**
   - http://localhost:8080/health → `{"status": "ok", "policy": {"version": 3, "status": "LOADED"}, "provider": {"name": "ollama", "model": "qwen2.5:7b"} | mock}`
   - http://localhost:8090/agent/health
   - http://localhost:5173 → Sign-in page

## 3. Sign In (1 minute)

Navigate to **http://localhost:5173**.

**Sign-in page:** Lists demo users.

Select **Anna Kowalska** (Developer, Kraków PL).

- Token issued with `role: developer`, `location: Krakow, PL`, `region: PL`
- Budget header shows `3,420 / 10,000 tokens`
- Provisioned tools: github, ci, logs-db, jira (sidebar)

## 4. Employee Chat (3 minutes)

Type a prompt in the chat box:

```
Why did the login tests fail last night? Check the CI run and logs.
```

**Expected behavior:**

The demo agent calls three tools in sequence:

1. **`ci.get_run`** (Allowed)
   - Tool provisioned for Developer role
   - Card shows green "ALLOWED"

2. **`logs-db.query`** (Masked)
   - Tool call succeeds
   - Response contains emails
   - DLP detects `[email]` pattern
   - Card shows orange "MASKED" – "DLP · pii_masking · 3 emails masked"
   - Budget increases: `3,420 + 142 = 3,562 tokens`

3. **`hr-db.find_approver`** (Blocked)
   - Tool NOT provisioned for Developer role
   - Card shows red "BLOCKED" – "Authorization · role_provisioning"
   - No further call attempted

4. **Approval Card**
   - If the agent tries a destructive action (e.g., "delete the stale branch")
   - Card shows blue "ESCALATED" with Approve/Reject buttons
   - Click Approve → executes and audited
   - Click Reject → dropped

## 5. Live Feed (1 minute)

Click **Admin** tab → **Live Feed**.

Shows real-time KPI cards:
- Total calls: 3
- Allowed: 1
- Blocked: 1
- Masked: 1
- Escalated: 0

Table lists each call:
- Time
- User · Role
- Tool call (e.g., `ci.get_run`, `logs-db.query`)
- Status
- Reason (e.g., "Matches roles.developer", "3 emails masked", "HR database not provisioned")

Filters at top: filter by User, Role, Status.

## 6. Audit Log and Call Detail (2 minutes)

Click **Audit Log** tab.

Table shows all calls with:
- Time
- User · Role
- Tool / LLM
- Status
- Rule ID
- Reason
- Tokens / Cost
- Proxy latency / Upstream latency

Click a row (e.g., the masked call) → **Call Detail** page.

Shows:
- **Metadata grid:** call_id, timestamp, identity, mcp_server, rule matched
- **Matched rule YAML:** the exact rule from policy.yaml
- **Request:** tool name, arguments
- **Response comparison:**
  - Raw (before masking): "02:11:04 401 invalid_token user=t.lis@example.com"
  - Delivered (after masking): "02:11:04 401 invalid_token user=[EMAIL_1]"
- **Per-stage timing bar:** Identity (0.1 ms) → Authorization (0.2 ms) → DLP (1.1 ms) → ... → Audit (0.3 ms)
  - DLP takes longest (regex + masking)

**Export buttons:**
- Export JSON: full call record
- Close

## 7. Policy Page (1 minute)

Click **Admin** → **Policy** tab.

Shows:
- **Version badge:** v3 (green LOADED or red ERROR if invalid)
- **Loaded at:** timestamp of last reload
- **Profile:** balanced (strict / balanced / permissive)
- **Rules by stage:**
  - **Authorization:** role_provisioning, data_residency
  - **DLP:** pii_masking, secrets_detection, external_send_after_untrusted_read
  - **Policy:** prompt_injection_signatures, prompt_injection_ml, llm_judge, ...
  - **Behavior:** rate_limit, loop_guard, circuit_breaker
  - **Resource:** (budgets in config)

Each rule shows:
- ID
- On (interception points)
- Type
- Action
- OWASP IDs

## 8. Live Policy Edit (1 minute)

Edit `Backend/config/policy.yaml`:

**Example 1: Disable PII masking**

Open file, find:
```yaml
- id: pii_masking
  on: [response]
  detect: [email, phone, pesel, iban, pan]
  action: mask
```

Change to:
```yaml
- id: pii_masking
  on: [response]
  detect: [email, phone, pesel, iban, pan]
  action: block
```

**Expected:** Within 1 second, Policy page version bumps to v4, status stays LOADED. Next `logs-db.query` is rejected with 403 "DLP · pii_masking" (blocked instead of masked).

**Example 2: Invalid YAML**

Add a syntax error:
```yaml
- id: broken
  on: [prompt
  # missing closing bracket
```

Save. Within 1 second:
- Policy page shows v5 ERROR (red)
- Last good policy (v4) still enforced
- Alert emitted in live feed: "Policy reload failed"
- Calls still work with v4 policy

Fix the YAML; version returns to green LOADED.

## 9. Attack Suite (1 minute)

In the admin panel, click **Attack Suite** card.

Panel shows scenario list:
- Positive cases (should be ALLOWED/PASSED)
- Negative cases (should be BLOCKED/STOPPED at expected stage)

Click **Run (Scripted)** button.

Scenarios execute in real time, SSE updates status:
- PENDING → RUNNING → STOPPED (blocked as expected) / PASSED (allowed as expected) / ERROR

Expected results:
- `developer_reads_ci_allowed`: PASSED
- `developer_reads_hr_db_blocked`: STOPPED at Authorization
- `prompt_injection_signature_blocked`: STOPPED at Policy
- `rate_limit_exceeded`: STOPPED at Behavior
- Etc.

**Scripted tier:** All deterministic (mock provider). No model dependency.

**Ollama tier (if available):** Click **Run (Ollama)**. Same scenarios sent as natural language to real Ollama agent. Slower, but shows real model behavior.

## 10. Self-Testing Suite (Optional, 2 minutes)

In terminal:

```powershell
cd Backend
python -m pytest -q --cov=control_layer --cov-report=term-missing
```

Expected: **pytest passed** with coverage > 80%.

```bash
python attack_suite.py --target http://localhost:8080
```

Expected: All scenarios pass. Exit code 0.

```bash
python attack_suite.py --target http://localhost:8080 --agent ollama
```

Expected: All scenarios pass (or NOT_ATTEMPTED for model non-compliance). Exit code 0.

## Evaluation Checklist

- [ ] Bootstrap completed without errors (or with acceptable Ollama skip)
- [ ] All three servers running (health endpoints respond)
- [ ] Sign in as Anna → see chat and tools sidebar
- [ ] Chat with three tools: 1 ALLOWED, 1 MASKED (DLP), 1 BLOCKED (Authorization)
- [ ] Live feed shows calls with KPI counters
- [ ] Audit log shows call detail with raw vs delivered response
- [ ] Policy page shows v3 LOADED with rules by stage
- [ ] Edit policy (disable masking) → within 1s, policy reloads, next call blocked
- [ ] Invalid policy → ERROR badge, reverts to last good
- [ ] Attack suite (scripted) all scenarios pass
- [ ] (Optional) Attack suite (Ollama) all scenarios pass

## Troubleshooting

### Ollama model not found
```
CTRL_MODEL_PROVIDER=auto
GET /health → provider: mock
```
Control layer falls back to mock provider. Scripted demo still works. Set `CTRL_MODEL_PROVIDER=mock` explicitly if needed.

### Redis connection refused
```
CTRL_REDIS_URL=redis://localhost:6379/0 (auto-fallback if unreachable)
GET /health → cache: memory
```
All state (budgets, sessions, cache) in-memory. Resets on restart.

### Frontend port 5173 already in use
Kill process on port 5173 or set environment variable before running:
```powershell
$env:PORT = 5174
.\scripts\run_dev.ps1
```

### pytest failures
Run with verbose output:
```bash
python -m pytest -vv tests/unit/application/
```

### attack_suite.py not found
Ensure working directory is repo root:
```bash
cd C:\Users\Kuba\Documents\IA-Controled-Layer
python attack_suite.py --target http://localhost:8080
```

## Next Steps

- Explore the codebase: [Architecture](architecture.md)
- Deep-dive policy tuning: [Policy Reference](policy-reference.md)
- OWASP coverage: [OWASP Mapping](owasp-mapping.md)
- Production deployment: [README](../../README.md)

---

**Questions?** Check the logs:
- Control Layer: terminal where `run_dev` started, or `/tmp/control_layer.log` (Linux)
- Frontend: browser DevTools console
- Audit: `Backend/audit/calls.jsonl` (JSONL log)
- Alerts: `Backend/alerts/alerts.xlsx` (Excel file)
