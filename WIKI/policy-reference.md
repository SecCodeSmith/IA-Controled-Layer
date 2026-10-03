# Policy Reference Guide

This guide documents the complete `policy.yaml` structure, how to tune it, and how hot reload works.

## Policy File Location and Reload

- **Location:** `config/policy.yaml` (relative to `Backend/`)
- **Reload:** The file watcher polls for changes every 1 second. On valid change, the version increments and the decision cache is cleared. Invalid YAML keeps the last good policy and emits an alert.
- **Environment override:** `CTRL_POLICY_FILE` (default: `config/policy.yaml`)

## Policy Document Structure

```yaml
version: 3
profile: balanced
models:
  allowed: [qwen2.5:7b, qwen2.5:3b, mock]
  pricing:
    qwen2.5:7b:
      input_per_1k_usd: 0.0002
      output_per_1k_usd: 0.0004
roles:
  developer:
    mcp_servers: [github, ci, logs-db, jira]
  hr:
    mcp_servers: [hr-db, calendar, mail]
  finance:
    mcp_servers: [payments, calendar]
    transaction_limit: 5000
    beneficiary_allowlist: []
locations:
  eu_customers:
    allowed_regions: [PL, DE, FR]
rules:
  # (see Rules section below)
  - { id: destructive_requires_approval, ... }
  - { ... }
budgets:
  per_user_tokens: 10000
  per_user_cost_usd: 1.00
  max_tokens_per_request: 2048
  upstream_timeout_s: 30
  warn_at_percent: 80
  on_exceeded: block
```

## Profile Levels

Three preset strictness profiles tune thresholds automatically. Each can be overridden per rule via the `threshold` or `block_at` / `escalate_at` fields.

### `strict` Profile
- **ML classifier:** block_at=0.7, escalate_at=0.4 (low tolerance for injection risk)
- **Budgets:** 80% of defaults, warn_at=70%
- **Rate limit:** 30 calls/min per user (half of balanced)
- **Loop guard:** 3 identical calls in 60s (strict repetition)

### `balanced` Profile (recommended)
- **ML classifier:** block_at=0.85, escalate_at=0.5
- **Budgets:** as stated (per_user_tokens=10000, per_user_cost_usd=1.00)
- **Rate limit:** 60 calls/min per user
- **Loop guard:** 5 identical calls in 60s

### `permissive` Profile
- **ML classifier:** block_at=0.95, escalate_at=0.7 (only high-confidence blocks)
- **Budgets:** 120% of defaults, warn_at=90%
- **Rate limit:** 120 calls/min per user (permissive)
- **Loop guard:** 10 identical calls in 60s

## Roles and Provisioning

Each role gets a list of `mcp_servers` it can access. Tool calls to unprovioned servers are blocked with `Authorization · role_provisioning`.

```yaml
roles:
  developer:
    mcp_servers: [github, ci, logs-db, jira]
  hr:
    mcp_servers: [hr-db, calendar, mail]
  finance:
    mcp_servers: [payments, calendar]
```

Additional role-specific limits (e.g., `transaction_limit`, `beneficiary_allowlist`) are enforced at the Policy stage.

## Locations and Data Residency

MCP tools can be tagged with a `data_region` (e.g., `eu_customers`). The Authorization stage checks that the user's allowed locations include the tool's region.

```yaml
locations:
  eu_customers:
    allowed_regions: [PL, DE, FR]
  us_only:
    allowed_regions: [US]
```

Tool registration in `mcp_servers.yaml`:
```yaml
tools:
  read: { tags: [], data_region: eu_customers }
```

A US-based user calling an `eu_customers` tool → **403 Authorization · data_residency**.

## Rules: Structure and Types

A rule matches conditions and produces an action. Type is inferred from context if omitted.

### Core Fields

- **`id`** (required): Unique rule identifier (e.g., `pii_masking`)
- **`on`** (required): Interception points as a list: `[prompt, response, tool_call, tool_result]`
- **`type`** (optional): `signatures`, `ml_classifier`, `llm_judge`, `detectors`, `sequence`, `residency`, `rbac`, `model_allowlist`, `tool_match`, `rate_limit`, `loop_guard`, `circuit_breaker`, `restricted_topics`, `unsafe_output`, `canary_token`
  - Inferred from other fields if absent (e.g., `detect` → `detectors`, `match.sequence` → `sequence`)
- **`action`** (required): `allow`, `flag`, `mask`, `block`, `require_approval`, `quarantine`
- **`stage`** (optional): Explicitly set pipeline stage if inference is wrong
- **`severity`** (optional): `info`, `warning`, `critical` (default: inferred from action)
- **`owasp`** (optional): List of OWASP IDs covered (e.g., `[LLM01, ASI01]`)

### Rule Type Reference

#### 1. `signatures` (Signature-based Injection & Exploits)

Matches text against a set of regex patterns from a feed file.

```yaml
- id: prompt_injection_signatures
  on: [prompt, tool_result]
  type: signatures
  feed: attack_signatures
  action: block
  owasp: [LLM01, ASI01]
```

- **`feed`**: Local file key (e.g., `attack_signatures` → `config/attack_signatures.yaml`), or HTTP URL via `CTRL_SIGNATURE_FEED_URL` (P1)
- **`categories`** (optional): Filter signatures by category (e.g., `[code_exec, deserialization]`)

#### 2. `ml_classifier` (ML First-Pass Detection)

Runs text through the Scikit-learn prompt injection classifier. Inconclusive scores escalate to the LLM judge.

```yaml
- id: prompt_injection_ml
  on: [prompt, tool_result]
  type: ml_classifier
  block_at: 0.85
  escalate_at: 0.5
  escalate_to: llm_judge
  owasp: [LLM01, ASI01]
```

- **`block_at`**: Confidence threshold for block (default per profile: strict 0.7, balanced 0.85, permissive 0.95)
- **`escalate_at`**: Threshold to escalate to judge (default per profile: strict 0.4, balanced 0.5, permissive 0.7)
- **`escalate_to`** (optional): Target rule id for escalation (default: `llm_judge`)

#### 3. `llm_judge` (LLM-Driven Safety Assessment)

Runs inconclusive or escalated text through an LLM judge (default: Ollama). Timeout → FLAG.

```yaml
- id: llm_judge
  type: llm_judge
  model: qwen2.5:7b
  timeout_s: 20
  on_timeout: flag
  owasp: [ASI01]
```

- **`model`**: Override default judge model (defaults to `CTRL_JUDGE_MODEL`)
- **`timeout_s`**: Hard timeout in seconds
- **`on_timeout`**: Action on timeout: `flag`, `block`, or `allow` (default: `flag`)

#### 4. `detectors` (PII & Secrets Detection)

Detects sensitive data patterns and masks or blocks.

```yaml
- id: pii_masking
  on: [response]
  detect: [email, phone, pesel, iban, pan]
  action: mask
  owasp: [LLM02]

- id: secrets_detection
  on: [prompt, response, tool_result]
  detect: [api_key, private_key, jwt]
  action: mask
  owasp: [LLM02]
```

- **`detect`**: List of patterns: `email`, `phone`, `pesel` (Polish ID), `iban`, `pan` (credit card), `api_key`, `private_key`, `jwt`
- **`action`**: `mask` replaces matches with `[TYPE_N]` (e.g., `[EMAIL_1]`); `block` rejects the call

#### 5. `sequence` (Exfiltration and Taint Propagation)

Blocks a tool call sequence (e.g., read then send external).

```yaml
- id: external_send_after_untrusted_read
  on: tool_call
  match:
    sequence: [read_external, send_external]
  action: block
  owasp: [ASI01, LLM02]
```

- **`match.sequence`**: List of tool tags (in order). Tags are defined in `mcp_servers.yaml` tool configs.
- Session is tainted after first match; subsequent sends are blocked.

#### 6. `residency` (Data Residency Control)

Enforced at Authorization stage; tool residency checked against user location.

```yaml
- id: data_residency
  on: tool_call
  type: residency
  action: block
  owasp: [ASI03, LLM02]
```

(Automatically triggered if tool has `data_region` in `mcp_servers.yaml`)

#### 7. `rbac` (Role-Based Access Control)

Enforced at Authorization stage; tool access checked against role provisioning.

```yaml
- id: role_provisioning
  on: tool_call
  type: rbac
  action: block
  owasp: [ASI03, LLM06]
```

(Automatically triggered via roles → mcp_servers mapping)

#### 8. `tool_match` (Custom Tool Rules and Approval)

Matches tool calls by name or action and enforces custom rules.

```yaml
- id: destructive_requires_approval
  on: tool_call
  match:
    action: [delete_*, push_main, drop_*]
  action: require_approval
  owasp: [ASI02, ASI09]

- id: transaction_limit
  on: tool_call
  match:
    tool: [payments.transfer]
    action: [transfer]
  limit: 5000
  owasp: [ASI02, LLM06]
```

- **`match.action`**: Glob patterns for tool action names (e.g., `delete_*`)
- **`match.tool`**: Specific tool names (e.g., `payments.transfer`)
- **`limit`** (optional): Numeric limit for transactions (amount or count)

#### 9. `rate_limit` (Per-Minute Throttle)

Blocks user if they exceed calls per minute.

```yaml
- id: rate_limit
  on: [prompt, tool_call]
  per_minute: 60
  action: block
  owasp: [LLM10, ASI08]
```

- **`per_minute`**: Max calls per user per minute (default per profile: strict 30, balanced 60, permissive 120)

#### 10. `loop_guard` (Repetition Detection)

Blocks user if identical calls repeat too often.

```yaml
- id: loop_guard
  on: tool_call
  identical_calls: 5
  window_s: 60
  action: block
  owasp: [LLM10, ASI08]
```

- **`identical_calls`**: Threshold (default per profile: strict 3, balanced 5, permissive 10)
- **`window_s`**: Time window in seconds (default: 60)

#### 11. `circuit_breaker` (Quarantine on Block Burst)

Quarantines user after N blocks in a time window.

```yaml
- id: circuit_breaker
  blocks: 5
  window_s: 300
  action: quarantine
  owasp: [ASI10]
```

- **`blocks`**: Number of blocks to trigger quarantine
- **`window_s`**: Time window (5 blocks in 5 minutes → quarantine)

#### 12. `restricted_topics` (Financial/Sensitive Topics)

(P1) Restricts discussion of sensitive topics (e.g., financial advice for HR role).

#### 13. `unsafe_output` (Output Validation)

(P1) Detects unsafe patterns in model output (e.g., code execution, system prompt leakage).

#### 14. `canary_token` (Honeypot Tokens)

(P1) Embeds fake tokens in responses to detect exfiltration.

## Budgets Configuration

```yaml
budgets:
  per_user_tokens: 10000              # Token limit per user per day (resets at midnight UTC)
  per_user_cost_usd: 1.00             # Cost limit per user per day
  max_tokens_per_request: 2048        # Max tokens per single prompt
  upstream_timeout_s: 30              # Timeout for Ollama/model calls
  warn_at_percent: 80                 # Warn when 80% of budget used
  on_exceeded: block                  # block | warn
```

- **`warn_at_percent`**: If `on_exceeded: warn`, alerts emit at this threshold but calls proceed
- **`on_exceeded`**: `block` rejects calls with 403 when limit hit; `warn` allows but flags

## Worked Examples

### Example 1: Make PII Block Instead of Mask

Change the PII masking rule action from `mask` to `block`:

```diff
- id: pii_masking
  on: [response]
  detect: [email, phone, pesel, iban, pan]
- action: mask
+ action: block
```

**Effect:** Any response containing PII is rejected with 403 `DLP · pii_masking`. Callers receive an error instead of a masked response.

### Example 2: Add a New Destructive Pattern

Add a new tool-match rule to block a specific action:

```yaml
- id: block_user_deletion
  on: tool_call
  type: tool_match
  match:
    tool: [hr-db.delete_user]
  action: block
  owasp: [ASI02]
  severity: critical
```

**Effect:** Any call to `hr-db.delete_user` is rejected immediately. To allow with approval, change `action: require_approval`.

### Example 3: Lower the Per-User Budget

Reduce daily token limit from 10,000 to 5,000:

```diff
budgets:
- per_user_tokens: 10000
+ per_user_tokens: 5000
```

**Effect:** After 5,000 tokens today, new calls are rejected with 403 `Resource · budget_exceeded` (or warn, depending on `on_exceeded`).

## Rule Ordering and Caching

Rules are evaluated in **pipeline order** (fixed, not YAML order):

1. **Identity** (no rules)
2. **Authorization** (rbac, residency, model_allowlist, approval_gate)
3. **DLP** (detectors, sequence, canary)
4. **Policy** (signatures, ml_classifier, llm_judge, restricted_topics, unsafe_output, tool_match [non-approval], transaction_limit)
5. **Behavior** (rate_limit, loop_guard, circuit_breaker, anomaly)
6. **Resource** (budgets)
7. **Audit** (no rules)

**Decision Caching:** DLP and Policy stages are cacheable via decision cache. Key: `sha256(role | point | normalized_text) | policy_version`. Cache is cleared on any policy reload (version bump).

## Validation and Hot Reload

The policy file is validated on load with **Pydantic v2**:

- All YAML syntax is validated
- Rule types are inferred (or checked if explicit)
- Unknown fields cause validation errors
- Regex patterns in signatures are compiled; invalid regex → error

On validation error, the file watcher logs the error, keeps the last good policy, emits an alert, and the status badge shows `ERROR` on the Policy page.

To test a policy before deploying, validate locally:

```bash
python -c "import yaml; from control_layer.domain.models import PolicyDocument; \
  yaml.safe_load(open('config/policy.yaml')); \
  print('Valid policy')"
```

---

**See also:** [API Contract](api-contract.md), [Architecture](architecture.md), [OWASP Mapping](owasp-mapping.md)
