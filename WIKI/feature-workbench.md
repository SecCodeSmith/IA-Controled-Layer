# Feature contract: Workbench window

Binding for the backend, API, and dashboard. A live testing and debugging window showing every feature working in real time: trace a prompt or tool call through the seven-stage pipeline, see the decision-tree classifier and judge verdict, curate the training set, retrain the tree, and simulate resource filtering. All traces are audited like normal calls.

## How it works

### Workbench trace model

A trace is a real call through the control layer pipeline, identical to production calls except:

1. **Session identity:** Caller identified by session token `workbench:<actor>`, where `actor` is the demo user (`anna.kowalska`, `marek.nowak`, etc.). The identity stage resolves the token and sets the role from the user config.
2. **Audit kind:** All traces recorded as `kind=workbench` in the audit log and live feed (visible alongside normal calls).
3. **Side effects:** Traces have full side effects: rate/loop counters increment, anomaly markers move, stats count the trace. This allows judges to see real risk context before curating samples.
4. **No circuit-breaker escalation:** Repeated Workbench blocks do not quarantine the actor (existing circuit-breaker is skipped for Workbench traces).

### Prompt trace

Request:

```json
{
  "actor": "anna.kowalska",
  "kind": "prompt",
  "text": "Delete all test accounts",
  "force_verify": true
}
```

Flow:

1. Issue a token (via `IssueTokenUseCase`) scoped to session `workbench:anna.kowalska`
2. Create a context as `HandleChatCompletionUseCase` does (no prior messages, agent name as usual)
3. Set `ctx.metadata[FORCE_VERIFY_KEY] = true` (forces sampled tree positives to escalate to judge, even at low sample rates)
4. Run the real `pipeline.run(ctx)` through all seven stages
5. Record a `CallRecord` via `RiskService.record(kind=workbench, target="workbench:prompt")`
6. Return `TraceResponse` with all pipeline stages, violations, classifier trace, judge verdict

### Tool call trace

Request:

```json
{
  "actor": "marek.nowak",
  "kind": "tool_call",
  "tool_call": {
    "server": "github",
    "tool": "read_file",
    "arguments": {"repo": "web-app", "path": ".env"}
  }
}
```

Flow:

1. Delegate to `HandleToolCallUseCase.execute` (it runs the normal tool-call pipeline and records the call)
2. On `ControlLayerError` with a `call_id`, read the `decision` field (set by W2 on every control-layer error path)
3. On success, fetch `raw_result` and `delivered_result` from the audit record (JSON-parsed when possible)
4. Return `TraceResponse` with stages from both passes (tool_call decision + tool_result decision, each tagged with `point`), violations, delivered vs. raw side-by-side

### Stage strip rendering

`TraceResponse.stages` contains only the stages that actually ran (short-circuit happens at the first block/quarantine). Each stage shows:

- **Stage name** (Identity, Authorization, DLP, Policy, Behavior, Resource, Audit)
- **Action** (ALLOWED, BLOCKED, MASKED, FLAGGED, QUARANTINED)
- **First violation** rule_id and action (if multiple violations, show the first one)
- **Timing** (milliseconds, p50 of ~3ms overhead per stage)
- **Cache hit** flag (true if DLP/Policy decision served from cache)

Empty stages array means all seven stages were skipped (no call was made, identity error, etc.).

## Configuration

Both prompt and tool_call traces use the real pipeline with real evaluators, classifiers, judge, and audit. No special configuration; rules and thresholds apply as in production. Optional `force_verify: true` forces the tree's sampled positive check at the current verify_sample_rate (useful for testing low-rate trees).

### Demo actor setup

Workbench uses demo users from `Backend/config/users.yaml`:

```yaml
users:
  - sub: "anna.kowalska"
    name: "Anna Kowalska"
    role: "developer"
    email: "anna@seccodesmith.pl"
    location: "Kraków"
    region: "PL"
  - sub: "marek.nowak"
    name: "Marek Nowak"
    role: "hr"
    email: "marek@seccodesmith.pl"
    location: "Warszawa"
    region: "PL"
```

## Endpoints

### Trace endpoint

`POST /api/workbench/trace` (admin token required)

**Request:**

```json
{
  "actor": "anna.kowalska",
  "kind": "prompt",
  "text": "Delete the stale branch",
  "force_verify": false
}
```

or

```json
{
  "actor": "marek.nowak",
  "kind": "tool_call",
  "tool_call": {
    "server": "hr-db",
    "tool": "query",
    "arguments": {"sql_like": "SELECT * FROM employees"}
  }
}
```

**Response:**

```json
{
  "call_id": "call-uuid",
  "kind": "prompt",
  "status": "ALLOWED",
  "action": "allowed",
  "stage": null,
  "rule_id": null,
  "reason": null,
  "masked_text": null,
  "stages": [
    {
      "stage": "identity",
      "action": "allowed",
      "timing_ms": 1.2,
      "cache_hit": false,
      "violations": []
    },
    {
      "stage": "authorization",
      "action": "allowed",
      "timing_ms": 0.8,
      "cache_hit": false,
      "violations": []
    },
    {
      "stage": "policy",
      "action": "allowed",
      "timing_ms": 2.1,
      "cache_hit": false,
      "violations": [
        {
          "rule_id": "prompt_injection_tree",
          "action": "flag",
          "confidence": 0.87,
          "reason": "tree positive sampled for judge verification",
          "evidence": []
        }
      ]
    }
  ],
  "classifier_trace": {
    "rule_id": "prompt_injection_tree",
    "probability": 0.87,
    "band": "escalate",
    "sampled": true,
    "forced": false,
    "explanation": {
      "probability": 0.87,
      "model_type": "tree",
      "path": [
        {"feature": "contains_delete", "value": 1, "threshold": 0.5, "direction": "<="},
        {"feature": "token_length", "value": 3, "threshold": 100, "direction": ">"}
      ],
      "leaf": {
        "node_id": 42,
        "samples": 5,
        "positive_fraction": 0.8
      },
      "top_features": ["contains_delete", "contains_drop"]
    }
  },
  "judge": {
    "verdict": "allow",
    "confidence": 0.95,
    "reason": "operational phrasing, not an attack"
  },
  "training_sample_id": "sample-uuid",
  "raw_result": null,
  "delivered_result": null
}
```

### Resources endpoint

`GET /api/workbench/resources` (admin token required)

**Response:**

```json
{
  "roles": ["developer", "hr", "finance", "*"],
  "resources": [
    {
      "id": "github_repo_files",
      "server": "github",
      "tools": ["read_file"],
      "path_argument": "path",
      "records": null,
      "grants": {
        "developer": {
          "paths": {
            "allow": ["src/**", "docs/**", "README.md"],
            "deny": ["**/.env", "secrets/**", "**/*.pem"]
          },
          "columns": {
            "allow": null,
            "deny": []
          },
          "rows": {}
        },
        "*": {
          "paths": {"allow": [], "deny": []},
          "columns": {"allow": null, "deny": []},
          "rows": {}
        }
      }
    }
  ]
}
```

## Dashboard

### Workbench page (`/admin/workbench`)

Divided into three cards:

#### 1. Prompt Lab Card

- **Actor select:** Dropdown of demo users (anna.kowalska, marek.nowak)
- **Text input:** Textarea for the prompt to trace
- **Force judge toggle:** Checkbox to set `force_verify=true`
- **Trace button:** POST /api/workbench/trace with kind=prompt, shows result below

**Result display:**

- **Stage strip:** Seven chips showing each stage's action and first violation rule
- **Decision tree card:**
  - **Header:** "Tree probability: 0.87, band: escalate, sampled: true"
  - **Path:** List of decision-tree steps, each highlighted if the feature's value appears in the prompt text
    - Example: `contains_delete <= 0.5? NO → token_length > 100? YES → leaf (5 samples, 80% positive)`
  - **Leaf info:** Number of samples and positive fraction
  - **Top features:** Bar chart or list of top 3 features
  - Hidden if tree did not evaluate
- **Judge card:**
  - **Verdict:** "Allow" (green) | "Block" (red) | "Flag" (yellow)
  - **Confidence:** 0.95 (as percentage bar)
  - **Reason:** "operational phrasing, not an attack"
  - **Sample link:** Click to jump to the sample in the training set table (in-page anchor #sample-{id})
  - Hidden if no judge evaluation

#### 2. Judge-Managed Training Set Card

- **Status row:** "Tree F1: 0.919 | Model type: tree | Version 1 | Trained 2h ago | Counts: 12 accepted, 3 pending, 2 rejected"
- **Samples table:**
  - Columns: ID (truncated), Text (truncated), Label, Source, Status, Created, Reviewed by
  - Rows clickable to show full text in a modal
  - **Actions per row:**
    - Accept button (PATCH with status=accepted)
    - Reject button (PATCH with status=rejected)
    - Flip label button (0↔1, PATCH with label flipped)
  - Refetch list after PATCH success
- **Curate button:**
  - POST /api/classifier/samples/curate with default limit=20
  - Show summary modal: "20 reviewed, 12 accepted, 5 rejected, 3 relabelled, 0 refused"
- **Retrain panel:**
  - Checkbox: "Include pending samples in training"
  - Submit button: POST /api/classifier/retrain
  - Progress bar: Show `retrain_progress` events (training, evaluating, publishing)
  - Result display: "F1: 0.92, Swapped: yes, New version: 2, Trained: just now"
  - Error banner: On 409 "retrain already in progress, try again in 30s" or `retrain_failed` error message

#### 3. Resource Scope Card

- **Resource matrix table:**
  - Rows: resources (github_repo_files, hr_directory_rows, hr_employee_record)
  - Columns: Role (developer, hr, finance, *) with cells showing grants
  - Cell format: "paths: allow [src/**, ...], deny [**/.env, ...] | columns: deny [salary] | rows: region=$identity.region"
  - Role "*" shown as "default"
  - Empty cells: "no grant"
- **Resource simulator:**
  - **Inputs:** Actor (dropdown), Server, Tool, Arguments (JSON textarea)
  - **Submit button:** POST /api/workbench/trace with kind=tool_call
  - **Result:**
    - **Status badge:** ALLOWED (green) | BLOCKED (red, rule_id: resource_scope) | MASKED (yellow, rule_id: resource_projection)
    - **Raw vs. delivered JSON:** Side-by-side editors
      - Columns in violation reason "redacted: col1, col2" are struck through in raw
      - Row count indicator: "1 row filtered" (hidden if 0)
      - "Unchanged" label if no redaction
    - **Audit link:** `call_id` link to `/admin/audit/{call_id}`

## Tests & verification

### Frontend vitest

- `Workbench.test.tsx`: Page renders three cards
- `StageStrip.test.tsx`: Seven chips shown, "skipped" state on empty stages
- `DecisionTreeCard.test.tsx`: Path steps rendered, feature highlighted when value in text, leaf info shown
- `JudgeCard.test.tsx`: Verdict badge color, confidence bar, sample link anchor
- `SamplesTable.test.tsx`: Accept/reject/flip buttons send correct PATCH, list refetched
- `RetrainPanel.test.tsx`: SSE progress events update bar, 409 error shows banner
- `ResourceSimulator.test.tsx`: Form submits, raw/delivered displayed, columns redacted, rows filtered
- `useRetrainStream.ts`: SSE parsing, event handling, cleanup

### Backend integration tests

- `/api/workbench/trace` prompt: request → real pipeline → response with stages, classifier, judge
- `/api/workbench/trace` tool_call: request → real tool execution → response with raw/delivered, audit link valid
- `/api/workbench/resources` → roles list, resources with grants, "*" role present
- Trace side effects: rate/loop counters increment, stats count the trace, audit record created with kind=workbench
- 401 without admin token; 400 on malformed request (prompt without text, tool_call without spec)
- Sample recorded on judge allow with source=workbench

### Scenarios

All three resource-scope scenarios pass when traced via Workbench:

1. **dev_reads_allowed_repo_file:** anna.kowalska → `github.read_file("web-app", "src/app.py")` → ALLOWED
2. **dev_reads_env_file_blocked:** anna.kowalska → `github.read_file("web-app", ".env")` → BLOCKED (resource_scope)
3. **hr_query_projected:** marek.nowak → `hr-db.query(...)` → MASKED (resource_projection), salary redacted, DE row filtered

## Limitations & gotchas

### Decision-tree path highlighting

A feature is highlighted as "in text" if its value > 0 (for TF-IDF features, non-zero indicates presence). Token-based features are always highlighted when the word is found; continuous features (e.g., text length) are never highlighted.

### Redaction column parsing

The frontend parses the `resource_projection` violation reason to extract redacted column names using regex `/column\(s\) redacted: (.+)$/`. If the backend wording differs, only `lib/parseProjection.ts` needs updating.

### SSE stream lifetime

The `GET /api/classifier/retrain/{job_id}/stream` connection stays open until the job completes or fails. Clients must handle reconnection on network loss; the frontend uses `useEventSource` which auto-reconnects with exponential backoff.

### Audit record consistency

Workbench traces appear in the audit log and live feed with `kind=workbench`. They are sorted by timestamp like normal calls, so a burst of workbench traces may fill the feed temporarily. The coordinator can distinguish them by the `kind` filter on the audit page.

### Structured content in tool results

When a tool result is projected due to resource_projection, both `raw_result` (original JSON) and `delivered_result` (projected JSON) are returned. The frontend displays both side-by-side; a client parsing only one of them may miss the masking.

### Side effects in demo mode

Workbench traces have full side effects (rate limit counters, anomaly markers). On a live system, repeated Workbench traces can consume rate budgets. A "dry-run" mode without side effects could be added in future.

---

See also: [Decision-tree feedback loop](feature-decision-tree-feedback-loop.md) for training set curation · [Resource scope](feature-resource-scope.md) for path/row/column filtering · [Architecture](architecture.md) for pipeline details.
