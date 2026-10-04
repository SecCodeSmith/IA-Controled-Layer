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
    mcp_servers: [github, ci, logs-db, jira, mail]
  hr:
    mcp_servers: [hr-db, calendar, mail]
  finance:
    mcp_servers: [payments, calendar]
    transaction_limit: 5000
    beneficiary_allowlist: [PL61109010140000071219812874, DE89370400440532013000]
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
    mcp_servers: [github, ci, logs-db, jira, mail]
  hr:
    mcp_servers: [hr-db, calendar, mail]
  finance:
    mcp_servers: [payments, calendar]
    transaction_limit: 5000
    beneficiary_allowlist: [PL61109010140000071219812874, DE89370400440532013000]
```

Additional role-specific limits (e.g., `transaction_limit`, `beneficiary_allowlist`) are enforced at the Policy stage. Developer role can now use `mail` for sending messages.

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
- **`type`** (optional): `signatures`, `ml_classifier`, `decision_tree`, `llm_judge`, `detectors`, `sequence`, `residency`, `rbac`, `resource_scope`, `resource_projection`, `model_allowlist`, `tool_match`, `rate_limit`, `loop_guard`, `circuit_breaker`, `restricted_topics`, `unsafe_output`, `canary_token`
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
  categories: [prompt_injection, jailbreak, system_prompt_exfiltration, exfiltration]
  action: block
  owasp: [LLM01, ASI01]

- id: historical_exploits
  on: [prompt, tool_call, tool_result, response]
  type: signatures
  feed: attack_signatures
  categories: [code_exec, deserialization, supply_chain, destructive]
  action: block
  owasp: [ASI05, LLM03, ASI04]
```

- **`feed`**: Local file key (e.g., `attack_signatures` → `config/attack_signatures.yaml`), or HTTP URL via `CTRL_SIGNATURE_FEED_URL` (P1)
- **`categories`** (optional): Filter signatures by category. Common categories:
  - `prompt_injection`, `jailbreak`, `system_prompt_exfiltration`, `exfiltration` (injection tier)
  - `code_exec`, `deserialization`, `supply_chain`, `destructive` (exploit tier)

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

#### 2a. `decision_tree` (Decision Tree First-Pass with Sampled Judge Verification)

Runs text through a Scikit-learn decision tree classifier (depth 12, balanced classes). Positive verdicts are randomly sampled and re-evaluated by the LLM judge. Judge verdict is final, preventing benign false positives from turning FLAGGED.

```yaml
- id: prompt_injection_tree
  on: [prompt, tool_result]
  type: decision_tree
  block_at: 0.85
  escalate_at: 0.5
  verify_sample_rate: 0.2
  escalate_to: llm_judge
  owasp: [LLM01, ASI01]
```

- **`block_at`**: Confidence threshold for block (default per profile: strict 0.7, balanced 0.85, permissive 0.95)
- **`escalate_at`**: Threshold to escalate to judge (default per profile: strict 0.4, balanced 0.5, permissive 0.7)
- **`verify_sample_rate`**: Fraction of positives (0.0–1.0) randomly sampled for judge verification (deterministic per rule+point+text with salt from `CTRL_VERIFY_SAMPLE_SALT`, default 0.2)
- **`escalate_to`**: Target rule for escalation (default: `llm_judge`)
- Tree artifact: `src/control_layer/ml/artifacts/prompt_injection_tree.joblib` (gitignored, rebuilt by scripts)
- See [Feature: decision-tree feedback loop](../feature-decision-tree-feedback-loop.md) for training set curation and retrain endpoints

#### 3. `llm_judge` (LLM-Driven Safety Assessment)

Runs inconclusive or escalated text through an LLM judge (default: Ollama). Timeout → FLAG. Note: `on: []` means this rule runs only when escalated by another rule (e.g., `prompt_injection_ml`), not automatically at any interception point.

```yaml
- id: llm_judge
  on: []
  type: llm_judge
  model: qwen2.5:7b
  timeout_s: 20
  on_timeout: flag
  owasp: [ASI01]
```

- **`on`**: Empty list `[]` means this rule is only invoked via escalation from another rule
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

##### Reversible masking (session vault)

Masking a tool result such as `k.wrona@example.com` to `[EMAIL_1]` stops the model from ever seeing the address, but it also stops the model from using it (`mail.send(to="[EMAIL_1]")` would reach nobody). With a `vault` block the value flows HR-DB -> control layer -> mail without reaching the model:

```yaml
- id: pii_masking
  on: [response, tool_result]
  detect: [email, phone, pesel, iban, pan]
  action: mask
  vault: { ttl_s: 28800, restore: { email: [mail.send], phone: [mail.send] } }
  owasp: [LLM02]
```

- Placeholders become stable per session: the same value is always `[EMAIL_1]` in that session, a new value gets the next number. Mappings live in the cache under `vault:` and expire after `ttl_s` (default 28800).
- `restore` maps a detector kind (`email`, `phone`, `pesel`, `iban`, `pan`) to tool patterns (`server.tool`, `*` wildcards allowed). Just before the tool_call stage the control layer replaces placeholders of those kinds in the call arguments (strings, nested objects and lists) with the real values and reports the count as `items_restored`. The pipeline, the MCP call and the result stage work on the restored arguments.
- Guarantees: kinds not listed for that tool stay literal text; secrets (`api_key`, `private_key`, `jwt`) can never be listed and are never stored; a placeholder from another session or unknown to the vault is left unchanged; the audit record keeps the arguments as the model sent them (placeholders) while the raw tool result shows admins the real value; an approved call is restored when it is executed; demo reset (full and behavior scope) wipes the vault.
- Only kinds listed under `restore` are stored in the vault; other kinds keep the plain per-text numbering. An invalid kind or pattern makes the policy fail validation (the last good policy stays active) and edits are hot-reloaded like any other rule.

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

#### 7a. `resource_scope` (File Path and Tool Argument Scope)

Enforced at Authorization stage; checks that tool arguments (file paths) are within the role's granted scope. Matched against the `path_argument` field in `resources:` configuration.

```yaml
- id: resource_scope
  on: tool_call
  type: resource_scope
  action: block
  owasp: [ASI03, LLM06]
  severity: high
```

- Blocks with 403 `Authorization · resource_scope` if argument path matches deny patterns or does not match allow patterns
- Reason includes the pattern and path: "path denied by pattern: secrets/**"
- Configured per resource in `resources:` section (see below)
- See [Feature: resource scope](../feature-resource-scope.md) for full path glob semantics

#### 7b. `resource_projection` (Row and Column Filtering)

Enforced at Resource stage on tool results; filters rows and redacts columns based on the role's grant. Masking is reported as `Authorization · resource_projection, status MASKED`.

```yaml
- id: resource_projection
  on: tool_result
  type: resource_projection
  action: mask
  owasp: [LLM02, ASI03]
```

- Filters rows matching row-scope predicates (e.g., `region: "$identity.region"`)
- Redacts columns in the deny list
- Reason: "N row(s) filtered, M column(s) redacted: col1, col2"
- Configured per resource in `resources:` section (see below)
- See [Feature: resource scope](../feature-resource-scope.md) for full filtering semantics

#### 8. `tool_match` (Custom Tool Rules and Approval)

Matches tool calls by name or action and enforces custom rules.

```yaml
- id: direct_push_to_main
  on: tool_call
  match:
    action: [push_main]
  action: block
  owasp: [ASI02, LLM06]
  severity: high

- id: destructive_requires_approval
  on: tool_call
  match:
    action: [delete_*, drop_*]
  action: require_approval
  owasp: [ASI02, ASI09]
```

- **`match.action`**: Glob patterns for tool action names (e.g., `delete_*`)
- **`match.tool`**: Specific tool names (e.g., `payments.transfer`)
- **`severity`** (optional): `info`, `warning`, `high`, `critical`

#### 8a. `transaction_limit` (Financial Transaction Control)

Limits financial transactions per user and enforces beneficiary allowlists.

```yaml
- id: transaction_limit
  on: tool_call
  type: transaction_limit
  tool: payments.transfer
  action: block
  owasp: [ASI02, LLM06]
  severity: critical
```

- Limit and beneficiary list are enforced per role (defined in `roles.finance`):
  - **`transaction_limit`**: Max transaction amount (e.g., 5000 in role config)
  - **`beneficiary_allowlist`**: List of allowed recipient IBANs
- Exceeding either triggers a block with 403 `Policy · transaction_limit`

#### 9. `model_allowlist` (Model Authorization)

Restricts which models the user may invoke (enforced at Authorization stage).

```yaml
- id: model_allowlist
  on: prompt
  type: model_allowlist
  action: block
  owasp: [LLM03, ASI04]
  severity: medium
```

- Model list comes from `models.allowed` in policy root (e.g., `["qwen2.5:7b", "qwen2.5:3b", "mock"]`)
- Block if user requests a model not in the list with 403 `Authorization · model_allowlist`

#### 11. `rate_limit` (Per-Minute Throttle)

Blocks a user who exceeds `per_minute` calls in a sliding 60-second window (counted in 10-second
buckets per user, so a burst that straddles a clock-minute boundary is still limited).

```yaml
- id: rate_limit
  on: [prompt, tool_call]
  per_minute: 60
  action: block
  owasp: [LLM10, ASI08]
```

- **`per_minute`**: Max calls per user per minute (default per profile: strict 30, balanced 60, permissive 120)

#### 12. `loop_guard` (Repetition Detection)

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

#### 13. `circuit_breaker` (Quarantine on Block Burst)

Quarantines user after N blocks in a time window. Enforced at Authorization stage to prevent cascading blocks.

```yaml
- id: circuit_breaker
  stage: authorization
  blocks: 5
  window_s: 300
  action: quarantine
  owasp: [ASI10, ASI08]
```

- **`blocks`**: Number of blocks to trigger quarantine (e.g., 5)
- **`window_s`**: Time window in seconds (e.g., 300 seconds = 5 minutes)
- **`stage: authorization`**: Explicit stage to ensure early evaluation (prevents rule cascade)

#### 14. `anomaly` (First-Time Destructive Use)

Flags when a user makes a destructive tool call they have never made before (first use anomaly detection).

```yaml
- id: anomaly_first_destructive_use
  type: anomaly
  on: tool_call
  action: flag
  owasp: [ASI10]
```

- Tracks user's first destructive action (delete, drop, push_main, etc.) per session
- Does not block, only flags for audit and escalation
- Paired with behavioral monitoring (circuit_breaker) to prevent abuse

#### 15. `restricted_topics` (Financial/Sensitive Topics)

(P1) Restricts discussion of sensitive topics (e.g., financial advice for HR role).

#### 16. `unsafe_output` (Output Validation)

(P1) Detects unsafe patterns in model output (e.g., code execution, system prompt leakage).

#### 17. `canary_token` (Honeypot Tokens)

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

## Resources Configuration

Fine-grained resource authorization beyond role-to-server mapping: per-role file-path scopes on tool arguments and row/column visibility on tool results.

```yaml
resources:
  - id: github_repo_files
    server: github
    tools: [read_file]
    path_argument: path
    roles:
      developer: { paths: { allow: ["src/**", "docs/**", "README.md"], deny: ["**/.env", "secrets/**", "**/*.pem"] } }
  
  - id: hr_directory_rows
    server: hr-db
    tools: [query]
    records: rows
    roles:
      hr: { columns: { deny: [salary] }, rows: { region: "$identity.region" } }
  
  - id: hr_employee_record
    server: hr-db
    tools: [get_employee]
    roles:
      hr: { columns: { deny: [salary] }, rows: { region: "$identity.region" } }
```

**Fields:**

- **`id`**: Unique resource identifier
- **`server`**: MCP server name (github, hr-db, ci, payments, etc.)
- **`tools`** (optional): List of tool names covered; empty means all tools on this server
- **`path_argument`** (optional): Name of the argument holding the file path (e.g., `path` in `read_file(repo, path)`)
- **`records`** (optional): Key holding the list of records in the result (e.g., `rows` in `{"rows: [...]}`); omit if the whole result is one record
- **`roles`**: Dict of role → grant mappings

**Grant structure** (per role):

```yaml
developer: 
  paths:
    allow: [glob patterns]  # If non-empty, path must match one of these; case-insensitive
    deny: [glob patterns]   # If path matches, it is denied (deny wins)
  columns:
    allow: [column names] | null  # null = all columns (default); [] = no columns
    deny: [column names]          # Columns to redact (default: [])
  rows:
    attribute: value | [values]   # Row predicate: field must match value(s) to pass
                                   # Supports $identity.region, $identity.role, $identity.sub, $identity.location
```

**Path scope semantics:**

- Allow/deny use glob patterns (`src/**`, `**/.env`, `secrets/**`)
- Paths normalized (backslash → forward slash, `..` rejected, absolute paths rejected)
- Deny-wins: if path matches both allow and deny, it is denied
- Allow-required: if allow list is non-empty, path must match it

**Row scope semantics:**

- Predicates are matched against fields in each record (as AND, all must match)
- `$identity.*` values are substituted per caller (region, role, sub, location from user config)
- Records lacking a predicate field do not match (filtered out)

**Column scope semantics:**

- Deny list redacts those columns (value → null in JSON)
- Allow list (if set) means only those columns are preserved
- Applied to all records in a result

For full reference, see [Feature: resource scope](../feature-resource-scope.md).

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
2. **Authorization** (rbac: role_provisioning, residency: data_residency, model_allowlist, circuit_breaker)
3. **DLP** (detectors: pii_masking + secrets_detection, sequence: external_send_after_untrusted_read, canary_token [P1])
4. **Policy** (signatures: prompt_injection_signatures + historical_exploits, ml_classifier: prompt_injection_ml, llm_judge, restricted_topics [P1], unsafe_output [P1], tool_match: direct_push_to_main + destructive_requires_approval, transaction_limit, anomaly: anomaly_first_destructive_use)
5. **Behavior** (rate_limit, loop_guard)
6. **Resource** (budgets)
7. **Audit** (no rules)

**Complete Rule List (17 total):**
- `direct_push_to_main`, `destructive_requires_approval` (Policy, tool_match)
- `pii_masking`, `external_send_after_untrusted_read` (DLP)
- `prompt_injection_signatures`, `prompt_injection_ml`, `llm_judge`, `historical_exploits` (Policy, injection detection)
- `transaction_limit` (Policy, financial control)
- `secrets_detection` (DLP)
- `model_allowlist` (Authorization)
- `data_residency` (Authorization)
- `role_provisioning` (Authorization)
- `rate_limit`, `loop_guard` (Behavior)
- `circuit_breaker` (Authorization, early evaluation)
- `anomaly_first_destructive_use` (Policy, behavior anomaly)

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
