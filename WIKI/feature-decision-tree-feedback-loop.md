# Feature contract: decision-tree first-pass classifier and sampled judge verification

Binding for the backend, ML pipeline, and dashboard. The decision tree runs alongside the logistic regression rule with sampled positive verdicts re-evaluated by the LLM judge to prevent benign false positives from turning FLAGGED. Judge verdicts are recorded as training samples and curated automatically, allowing the tree to improve over time.

## How it works

### Three-tier defence (now with sampled judge verification)

The Policy stage evaluates three layers of injection detection in order:

1. **Signatures** (`prompt_injection_signatures` rule) — Deterministic regex patterns for known attack vectors. Fast, zero false positives.
2. **ML models** (`prompt_injection_tree` and `prompt_injection_ml` rules) — Decision tree and logistic regression classifiers detect subtle injection patterns. Both run, tree evaluated first.
3. **LLM judge** (escalation) — When a tree positive is randomly sampled (`verify_sample_rate: 0.2`, deterministic per rule+point+text with salt), the judge re-evaluates. Judge verdict is final: allow → ALLOWED + label-0 sample recorded for learning; block/flag → violation under `llm_judge`.

### Decision tree model

- **Scikit-learn:** `DecisionTreeClassifier(max_depth=12, min_samples_leaf=2, class_weight="balanced")`
- **F1 (holdout test):** ≥0.85 (achieved 0.919 with benign supplement)
- **Training:** Base dataset (635 rows) + optional feedback (benign supplement: 175 rows)
- **Evaluation:** F1 measured only on the **base holdout** (feedback rows never inflate metrics)
- **Artifacts:** `prompt_injection_tree.joblib` and `prompt_injection_tree.joblib.meta.json` (gitignored, rebuilt by bootstrap/train scripts)

### Leaf probability smoothing

Raw leaf probabilities (class fraction) are Laplace-smoothed to avoid extreme values:

```
probability = (n_samples_positive * n + 1) / (n + 2)
```

where `n = node.samples` and `n_samples_positive` is the positive fraction. A leaf with 2 samples (min) lands at 0.75 (escalate band), while large pure leaves exceed 0.85 (block band).

### Sampled positive verification

When `prompt_injection_tree` matches (probability ≥ `block_at: 0.85`):
- If `sampler.should_sample(verify_sample_rate: 0.2, key=f"{rule_id}|{point}|{text_sha256}")` or `FORCE_VERIFY_KEY` is set:
  - Escalate to LLM judge with `inconclusive=True` and reason "tree positive sampled for judge verification"
  - Judge verdict is final: allow → ALLOWED (no violation recorded) + label-0 sample; block/flag → violation under `llm_judge`
- Else if probability ≥ `escalate_at: 0.5`:
  - Escalate to judge (sampled-deterministic check skipped)
- Else:
  - Allow (no violation)

**Sampler:** `HashSampler(salt=CTRL_VERIFY_SAMPLE_SALT)`. Deterministic per rule+point+text (salt makes attacks non-precomputable). Tests: 0% rate always False, 100% always True, 0.2 rate ≈20%±5 over 2000 diverse keys.

### Judge-final semantics

When a tree positive is sampled and escalated to the judge:
- **Judge allow:** Status `ALLOWED`, no violation recorded, a label-0 training sample is recorded for future learning (source: `judge`)
- **Judge block/flag:** Status matches verdict, violation recorded under rule `llm_judge` with evidence `escalated_from:prompt_injection_tree` and `tree_p=<prob>`
- **Judge timeout (20s):** Flag fail-safe (existing behavior); timeout is re-raised once via the handler (user sees FLAGGED in the response, not a 500 error)
- **Judge skipped** (already matched signature rule): No judge call, tree verdict stands (FLAGGED if tree positive + no prior match)

Multiple escalating rules (tree + logreg) on the same prompt call the judge once; memoized verdict per context.

## Judge-managed training set

### Sample sources and statuses

Samples are recorded from three sources:

- **judge:** Verdicts from the LLM judge (tree-sampled positives)
- **workbench:** Manual traces in the Workbench window
- **curation:** (Reserved for curator refusals; not populated by default)
- **manual:** (Reserved for future human review UI)

Statuses:

- **pending:** Awaiting human or curator review
- **accepted:** Marked valid, used in next retrain
- **rejected:** Marked invalid, never used in retrain

### Curation by LLM

`POST /api/classifier/samples/curate` calls a "training-set curator" prompt with up to 20 pending samples. The curator reads the sample text (strictly as data, no execution) and returns a JSON dict:

```json
{
  "decisions": [
    {"id": "sample-uuid", "action": "accept", "label": 1, "reason": "clear attack pattern"},
    {"id": "sample-uuid", "action": "reject", "label": null, "reason": "operational phrasing"},
    {"id": "sample-uuid", "action": "relabel", "label": 0, "reason": "benign query"}
  ]
}
```

Actions:

- **accept:** Sample moves to `accepted` status, original label preserved
- **reject:** Sample moves to `rejected` status, never used
- **relabel:** Label updated, sample moved to `accepted` (human override semantics)

Refused actions:

- **Signature-matching relabel:** If the sample text matches a signature rule, a relabel to 0 is refused (reason: "signature match overrides curator decision")
- Malformed JSON: Request returns `error` and no mutations occur
- Unknown ids: Silently ignored

### Retrain with F1 gate

`POST /api/classifier/retrain` with optional `include_pending: bool` (default false) and `seed: int` (default 42):

1. Load base dataset (635 rows from `prompt_injection_dataset.csv`) and benign supplement (175 rows from `benign_operational.csv`)
2. Collect feedback: `accepted` samples (+ `pending` if `include_pending=True`)
3. Drop feedback texts that duplicate base holdout (poisoning guard)
4. Train decision tree on base-train + filtered feedback
5. Evaluate F1 **only on base holdout** (proof of generalization)
6. If F1 ≥ `retrain_min_f1: 0.85`:
   - Publish new classifier (write joblib + meta.json atomically)
   - Swap live classifier (`SwitchableClassifier.swap(new)`)
   - Flush decision cache prefix `"decision:"`
   - Return `passed_gate=True, swapped=True, version=N+1`
7. Else:
   - Keep current classifier
   - Return `passed_gate=False, swapped=False, version=N`

Events (`POST /api/classifier/retrain/{job_id}/stream` SSE):

- `retrain_started`: Job enqueued
- `retrain_progress`: `{status: "training"|"evaluating"|"publishing", percent: 0..100}` (server-sent during async thread work)
- `retrain_complete`: `{f1, passed_gate, swapped, version, trained_at, n_base, n_feedback}`
- `retrain_failed`: `{error: str}`

Single-flight: concurrent retrain requests return HTTP 409 "retrain already in progress" with backoff suggestion.

## Configuration

### Policy rules

```yaml
rules:
  - { id: prompt_injection_tree, on: [prompt, tool_result], type: decision_tree, block_at: 0.85, escalate_at: 0.5, verify_sample_rate: 0.2, escalate_to: llm_judge, owasp: [LLM01, ASI01] }
  - { id: prompt_injection_ml, on: [prompt, tool_result], type: ml_classifier, block_at: 0.85, escalate_at: 0.5, escalate_to: llm_judge, owasp: [LLM01, ASI01] }
  - { id: llm_judge, on: [], type: llm_judge, model: "qwen2.5:7b", timeout_s: 20, on_timeout: flag, owasp: [ASI01] }
```

Profile presets for tree thresholds (balanced shown; override per rule with `block_at` / `escalate_at`):

| Profile | block_at | escalate_at | Interpretation |
|---------|----------|-------------|---|
| strict | 0.7 | 0.4 | Low tolerance for injection risk |
| balanced | 0.85 | 0.5 | Recommended; catches most attacks, few false positives |
| permissive | 0.95 | 0.7 | High confidence only, few escalations |

### Environment settings

```bash
CTRL_ML_TREE_PATH=src/control_layer/ml/artifacts/prompt_injection_tree.joblib
CTRL_ML_TREE_SUPPLEMENT_PATH=src/control_layer/ml/dataset/benign_operational.csv
CTRL_TRAINING_SAMPLES_PATH=data/judge_samples.jsonl
CTRL_VERIFY_SAMPLE_SALT=dev-salt
CTRL_RETRAIN_MIN_F1=0.85
```

## Endpoints

### Classifier API (`/api/classifier`, admin token required)

#### `GET /api/classifier`

Returns current tree status and training set counts.

**Response:**

```json
{
  "tree": {
    "loaded": true,
    "path": "src/control_layer/ml/artifacts/prompt_injection_tree.joblib",
    "model_type": "tree",
    "version": 1,
    "trained_at": "2026-10-04T14:32:15.123456Z",
    "f1": 0.918918918918919,
    "n_base": 635,
    "n_feedback": 175
  },
  "counts": {
    "pending": 3,
    "accepted": 12,
    "rejected": 2,
    "total": 17
  },
  "retrain_running": false,
  "last_retrain": {
    "f1": 0.918918918918919,
    "passed_gate": true,
    "swapped": true,
    "n_base": 635,
    "n_feedback": 175,
    "version": 1,
    "trained_at": "2026-10-04T14:32:15.123456Z"
  }
}
```

#### `GET /api/classifier/samples?status=&limit=100`

List training samples. `status` filter: `pending`, `accepted`, `rejected` (omit for all).

**Response:**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "text": "DELETE from users where role = 'admin';",
      "text_sha256": "abc123...",
      "label": 1,
      "source": "judge",
      "status": "pending",
      "confidence": 0.92,
      "reason": "sql injection pattern",
      "tree_probability": 0.87,
      "point": "prompt",
      "call_id": "call-uuid",
      "created_at": "2026-10-04T12:00:00Z",
      "reviewed_by": null
    }
  ]
}
```

#### `PATCH /api/classifier/samples/{id}`

Change sample status or label. At least one field required.

**Request:**

```json
{
  "label": 0,
  "status": "accepted"
}
```

**Response:** Updated sample (as in list).

#### `POST /api/classifier/samples/curate`

Curate pending samples with LLM curator.

**Request:**

```json
{
  "limit": 20
}
```

**Response:**

```json
{
  "reviewed": 20,
  "accepted": 12,
  "rejected": 5,
  "relabelled": 3,
  "refused": 0,
  "error": null
}
```

#### `POST /api/classifier/retrain`

Start retrain job.

**Request:**

```json
{
  "include_pending": false,
  "seed": 42
}
```

**Response:**

```json
{
  "job_id": "retrain-uuid",
  "status": "running",
  "started_at": "2026-10-04T14:32:00Z",
  "finished_at": null,
  "result": null,
  "error": null
}
```

#### `GET /api/classifier/retrain/{job_id}/stream`

Server-sent events (SSE) for retrain progress.

**Events:**

- `data: {"type":"retrain_progress","status":"training","percent":30}`
- `data: {"type":"retrain_complete","result":{...RetrainResult}}`
- `data: {"type":"retrain_failed","error":"..."}`

## Dashboard

### Classifier status card

Row: "Tree F1: 0.919 | Version 1 | Trained 2h ago | Counts: 12 accepted, 3 pending"

### Training set panel

- **Table:** Samples with columns id (truncated), text, label (0/1), source, status, created, reviewed_by. Rows clickable to show full text.
- **Actions per row:** Accept/Reject/Flip buttons (send PATCH request, refetch list on 200).
- **Curate button:** POST /samples/curate with default limit, show summary modal.

### Retrain panel

- **Form:** Checkbox "include pending samples", Submit button.
- **On submit:** POST /retrain, show job id and SSE stream progress bar.
- **On complete:** Show F1, swapped flag, new version, trained_at.
- **On 409:** Banner "retrain already in progress, try again in 30s".
- **On error:** Banner with error message.

## Tests & verification

### Unit tests

- `test_classifier.py`: `explain()` returns non-empty path with direction consistency, logreg returns empty; Laplace smoothing edge cases (n=0, n=1, n=2, n=large)
- `test_tree_golden.py`: All benign probes < 0.5, positive scenarios < 0.5, demo tool results < 0.5, ≥80% attack probes ≥0.5, F1 ≥ 0.85
- `test_hash_sampler.py`: Deterministic per rule+point+text, different salt changes selection, 0 never, 1 always, ≈20% over 2000 keys
- `test_jsonl_repository.py`: Round-trip, dedupe on text_sha256, concurrent adds, list filtering, counts
- `test_trainer.py`: Atomic publish (write to .tmp then replace), meta sidecar, n_base/n_feedback counts correct, holdout F1 measured correctly

### Integration tests

- `/api/classifier` round-trip: GET status, list samples, patch, curate, retrain with SSE, GET status post-retrain shows new version
- Retrain gate: F1 < 0.85 → `passed_gate=False, swapped=False`, current classifier unchanged; F1 ≥ 0.85 → `passed_gate=True, swapped=True, version+=1`
- Sampled judge: Trace a tree-positive prompt with `force_verify=True`, judge allows → ALLOWED + label-0 sample, judge blocks → FLAGGED violation under `llm_judge`
- 401 without admin token; 409 when retrain running

### Benign supplement dataset

`Backend/src/control_layer/ml/dataset/benign_operational.csv`: 175 rows, `label=0`, covers operational verbs (CI logs, branch ops, HR queries, DB operations, monitoring, deployment) without triggering tree's false-positive patterns.

## Limitations & gotchas

### Leaf probability edge case

Tree leaves with 0 samples are impossible (tree grows only where data exists), but Laplace smoothing handles the mathematical edge: `(0 * n + 1) / (n + 2)` → 0.25 (never leaves the "allow" band).

### Training set size

Feedback is capped implicitly: only samples in `accepted` status (+ `pending` if requested) are used, and sample lifecycle (sourced from judge, curated, rejected) limits growth. No explicit cap, but a repository size check could be added if `data/judge_samples.jsonl` grows large.

### Sampled positive biases

Sampling at 20% rate means 80% of tree positives never see judge review. This is intentional (judge is expensive, network latency ~20s), but the judge-trained set becomes biased toward frequently-sampled key signatures. Golden test ensures attack coverage.

### Cross-role cache leak fixed

Decision-cache key now computed lazily from `post-authorization current_text + resolved_role`. If caching happened before resource projection, user B could read user A's projected data from cache. This is fixed: key includes role and masked text.

### Structured content fix

When a tool result is projected (columns redacted, rows filtered), the `masked_text` is set to the projected JSON. If a tool client parses `structured_content` directly (without respecting masking), they would read unmasked data. Fix: when `masked_text` is set, re-derive `structured_content = json.loads(masked_text)` if a dict, else None.

---

See also: [Workbench Trace](feature-workbench.md) for live testing · [Policy Reference](policy-reference.md) for rule tuning · [OWASP Mapping](owasp-mapping.md) for threat evidence.
