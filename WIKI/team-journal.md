# Team Journal — AI Control Layer Development Log

**Project:** HackYeah 2026 — AI Control Layer  
**Deadline:** 2026-10-04 23:00  
**Last updated:** 2026-10-04 02:40

## Decision Log

### Phase 0 — Architecture & Contracts (2026-10-04 02:15)

| Date | Decision | Why | Owner |
|------|----------|-----|-------|
| **2026-10-04 02:15** | **Decision trees run alongside logreg** (tree first), not replacing it | Gives both rule coverage during transition; tree's high false-positive rate (operational verbs) mitigated by sampled judge verification + benign supplement + golden test. Decision cache remains unchanged (same pipeline, no branching). | User (Fable) |
| **2026-10-04 02:15** | **Judge verdict is final** for sampled tree positives | Prevents tree false positives from turning FLAGGED. Judge block/flag still recorded as violation under `llm_judge`. Judge allow + tree positive → ALLOWED + label-0 sample for future learning. Delivered content never changes. | User (Fable) |
| **2026-10-04 02:15** | **Row/column projection reported as `Authorization · resource_projection, status MASKED`** | Never silent (user expects masking visibility). Distinct from `pii_masking` (DLP stage). Changes `masked_text` in audit record; no change to delivered content semantics (already applies masks or blocks). | User (Fable) |
| **2026-10-04 02:15** | **Workbench traces run the real pipeline, audited like normal calls** | Visible in live feed + audit log, counted in stats + risk scoring. Authenticates session with `workbench:<actor>` token; calls are real (not previews), so side effects occur (rate/loop counters move, anomaly markers set). Allows judges to see full context before curation. | User (Fable) |

### Verified Facts (Exploration + Senior Review + Live Probes)

| Fact | Impact | Mitigation |
|------|--------|-----------|
| `*.joblib` under `ml/artifacts/` is **gitignored**; built by `bootstrap.ps1`, `train_ml.ps1`, `Dockerfile` | Tests cannot depend on pre-built tree; must train in-session or skip | `tests/conftest.py::make_settings` points artifact paths into temp dirs; worktrees must run pytest with `PYTHONPATH=src` |
| `prompt_injection_ml` rule defaults to `action: flag` (no `action:` field) | Tree inherits `flag`, so "block band" means FLAGGED (delivered content identical) | Keep delivered content never-silent; reason logged + visible in audit |
| Tree F1 0.885 on current dataset (depth 12, min-leaf 2) but leaf probs are {0, 0.56, 1}; escalate band almost never fires | Escalate-band verification path nearly dead; must use sampling | Hash sampler with salt (deterministic per `rule\|point\|text`, replicable in tests) for positive sampling at 0.2 rate |
| Tree false-positives on benign operational verbs (e.g., "Delete the stale branch…" → 1.0) | Would turn positive scenarios FLAGGED | Benign supplement dataset (`ml/dataset/benign_operational.csv`) + golden test ensuring tree scores benign probes < 0.5 |
| `tests/unit/domain/policy/test_parser.py:36-61` asserts 17 rules and exact id→stage map; `CallKind` set asserted separately | New rules (tree, resource_scope, resource_projection) must be added to assertions | Phase 0 updates: assert 19 rules, 3 new EXPECTED_TYPES (decision_tree, resource_scope, resource_projection), add `CallKind.workbench` |
| `ProcessingPipeline._build_cache_key` runs before DLP/Policy, uses `anonymous` role + raw text; masked DLP/Policy bundle carries full `masked_text` | User B can read user A's projected rows from cache if both call same tool on overlapping data | **Critical fix:** key computed lazily before first cacheable stage from `post-authorization current_text + resolved_role` (existing tests must stay green) |
| `glob.translate("src/**")` matches `src/../secrets/x` and `src/.env`; path checks lack normalization | Directory traversal / absolute path bypass possible | `pathlib.PurePosixPath.resolve()` + normalization, reject `..`/absolute/drive, case-folding, deny-wins semantics |
| `handle_tool_call.py` returns unmasked `structured_content` to structured clients | PII leak for clients parsing JSON directly | When `ctx2.masked_text` is set, re-derive `structured_content = json.loads(masked_text)` if dict, else None |
| Resource projection runs after role provisioning but before DLP; if DLP then projects again, duplicate filters | Row/column logic tangled with DLP; ordering unclear | Place resource rules **after** role_provisioning; `resource_scope` (tool_call, block) before DLP; `resource_projection` (tool_result, mask) runs between DLP-filtered result and Behavior stage |

### Risk Mitigations

| Risk | Mitigation | Testable By |
|------|-----------|-----------|
| Tree false positives turn attack scenarios FLAGGED | Benign supplement dataset + golden test (tree F1 ≥0.85, benign < 0.5) | `tests/unit/ml/test_tree_golden.py` |
| Judge unavailable → sampling positive loses escalation path | Existing flag fail-safe (tree action: flag); judge timeout → flag | Manager single-flight circuit; judge mock provider always returns; mock curator accepts-all |
| Retrain overwrites gitignored artifact; bootstrap rebuilds | Not a risk; artifacts are ephemeral | Test conftest seeds a session-trained tree (base + supplement, seed 42) per run |
| PII reaches `judge_samples.jsonl` | Text truncated to 2000 chars; file gitignored; documented | Text field in `TrainingSample` model enforces 2000-char limit; WIKI warning in Feature docs |
| Path `glob.translate` false negatives / traversal bypasses | Normalize → `posixpath.normpath`, reject `..`/absolute/drive, case-fold, deny-wins | `tests/unit/application/resources/test_path_scope.py` covers all cases |
| Cache-key leak: user B sees user A's projected rows | Lazy key computation from post-auth text + resolved role | `tests/unit/application/test_pipeline_cache_key.py` asserts different keys for different roles + projected text, same key for repeated calls |

---

## Hand-off Notes (From Streams)

*(This section will be filled as each stream (W1, W2, W3, J1, J2) completes and submits its hand-off note.)*

### W1 — F1 Backend (Opus)

*Pending — expected ~11:00 checkpoint*

### W2 — F2 Backend + Workbench API (Sonnet)

*Pending — expected ~10:00 checkpoint*

### W3 — F3 Frontend (Sonnet)

*Pending — expected ~11:30 checkpoint*

### J1 — ML + Adapters + Scripts (Haiku)

*Pending — expected ~07:15 checkpoint*

### J2 — Demo Data + Scenarios (Haiku)

*Pending — expected ~07:15 checkpoint*

---

## Key Files & Ownership (Phase 0 → Phase 4)

| File | Owner | Frozen After | Notes |
|------|-------|----------|--------|
| `Backend/config/policy.yaml` | Fable (all phases) | Phase 0 | Shared contract: all rules, resource scopes, hot-reload validation |
| `Backend/src/control_layer/domain/models/{classifier,training_sample,resource}.py` | Fable + Opus (review) | Phase 0 | Domain contracts, no changes post-Phase 0 |
| `Backend/src/control_layer/application/evaluators/__init__.py` | Fable + Opus (phase 0) | Phase 0 | build_evaluators factory, all evaluators wired |
| `Backend/src/control_layer/presentation/wiring/composition_root.py` | Fable + Opus (phase 0) | Phase 0 | Dependency injection, module wiring |
| `tests/conftest.py` | Fable (phase 0) | Phase 0 | Settings, fixtures, artifact paths |
| W1 files (F1 classifier, retrain, API) | Opus | Phase 2 | Classifier module, decision_tree evaluator, curation service, retrain job manager |
| W2 files (F2 resource, pipeline, Workbench API) | Sonnet | Phase 3 | Resource models, evaluators, cache-key fix, projection, API routes |
| W3 files (F3 frontend) | Sonnet | Phase 4 | Workbench page, cards, hooks, handlers |
| J1 files (ML, adapters, scripts) | Haiku | Phase 2 | Train.py updates, sampler, trainer, JSONL repo, bootstrap/train_ml scripts |
| J2 files (demo data, scenarios) | Haiku | Phase 2 | MCP fixtures, scenario bodies, test catalogue |

---

## Checkpoints & Sign-Offs

- **~04:15** Phase 0 contracts complete (Fable lead reviews)
- **~07:15** J1 + J2 complete, merged to main; full suite green
- **~10:00** W2 complete + tested (Fable verifies)
- **~11:00** W1 complete + retrain verified (Fable verifies, attack suite green)
- **~11:30** W3 complete + frontend tests pass (Fable verifies)
- **~14:00** All streams merged; full suite + attack suite 27/27 green; docs complete
- **~23:00** Deadline submission

---

**See also:** [CLAUDE.md](../CLAUDE.md) (dev guide) · [Architecture](architecture.md) · [Policy Reference](policy-reference.md)
