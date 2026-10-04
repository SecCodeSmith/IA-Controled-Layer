# CLAUDE.md — AI Control Layer Development Guide

**Project:** HackYeah 2026 — AI Control Layer (seven-stage policy proxy)  
**Deadline:** 2026-10-04 23:00  
**Team:** SecCodeSmith

## Purpose

A policy-enforcing proxy gateway that sits between AI agents and backend services (Ollama, MCP servers). It implements a **seven-stage deterministic + AI-driven processing pipeline** with hot-reloadable policy, real-time audit, hybrid threat detection (signatures + ML classifier + LLM judge), and OWASP-grounded controls. Every call flows through the fixed order: **Identity → Authorization → DLP → Policy → Behavior → Resource → Audit** (never reorder).

**Key docs:** [Judges Quickstart](WIKI/judges-quickstart.md) (10 min intro) · [Architecture](WIKI/architecture.md) (pipeline + diagrams) · [Policy Reference](WIKI/policy-reference.md) (rule types, hot-reload) · [OWASP Mapping](WIKI/owasp-mapping.md) (threat coverage) · [API Contract](WIKI/api-contract.md) (endpoints + schemas) · [Demo Script](WIKI/demo-script.md) (6-min walkthrough)

## Architecture & Clean Code Rules

**Clean Architecture layers** (dependency rule: domain imports nothing; application imports domain; infrastructure implements domain ports; presentation is adapter composition):
- **Domain:** `domain/{models,ports,policy}` — Pydantic frozen models, Protocol ports, parser rules
- **Application:** `application/{evaluators,services,use_cases}` — Business logic, orchestration, no frameworks
- **Infrastructure:** `infrastructure/{ml,providers,repositories,audit}` — Database/ML/HTTP adapters, SOLID
- **Presentation:** `presentation/{api,wiring,main.py}` — FastAPI routes, schema mapping, no business logic

**Seven-stage order** (validated at startup via `ProcessingPipeline._validate_stage_order` against `StageName.ordered()`): Identity → Authorization → DLP → Policy → Behavior → Resource → Audit. Stages 1, 2, 6, 7 always run. Stages 3–4 (DLP, Policy) cacheable.

**Rule type → evaluator:** Each rule in `policy.yaml` has a `type` field (e.g., `rbac`, `residency`, `model_allowlist`, `tool_match`, `resource_scope`, `resource_projection`, `detectors`, `sequence`, `canary_token`, `signatures`, `ml_classifier`, `decision_tree`, `llm_judge`, `restricted_topics`, `unsafe_output`, `transaction_limit`, `rate_limit`, `loop_guard`, `circuit_breaker`, `anomaly`). The `domain/policy/parser.py` defines type sets (`_DLP_TYPES`, `_AUTHORIZATION_TYPES`, `_POLICY_TYPES`, `_BEHAVIOR_TYPES`) and `infer_rule_type()`, `infer_stage()` functions. The `application/evaluators/build_evaluators()` function instantiates the right evaluator class per type and stage.

**Interception points:** `prompt` (agent text), `response` (model output), `tool_call` (agent → tool), `tool_result` (tool → agent). Each rule's `on: [...]` declares which points apply.

**Decision cache:** Implemented via `ProcessingPipeline._build_cache_key()`, keyed on `decision:{policy_version}:{sha256(role|point|normalized current_text)}`. Key is computed lazily right before the first cacheable stage (after Authorization), using the resolved role and post-authorization `current_text`, preventing cross-identity cache leaks. Cache stores full `DLP + Policy` bundle. `cache.flush("decision:")` runs on policy reload, protection changes, and classifier hot-swap.

**Hot-reload:** `config/policy.yaml` watched every 1 s. Valid YAML → version bumps, cache clears, new rules active. Invalid → ERROR badge, last good kept, alert emitted. No restart needed.

## Three New Features (Landed 2026-10-04)

1. **Decision-tree feedback loop** (`/api/classifier`, `/admin/workbench`): A Scikit-learn decision tree (depth 12, min-leaf 2, F1 ≥0.85) runs alongside the existing logreg rule; positive verdicts are randomly sampled and re-evaluated by the LLM judge (judge verdict is final); the judge's verdicts are recorded as labelled samples and curated by a "training-set curator" prompt; accepted samples retrain the tree, which is hot-swapped without restart. Prevents benign false positives (e.g., "Delete the stale branch") from turning FLAGGED. Tree positive + judge allow → ALLOWED + label-0 sample recorded for future learning.

2. **Resource scope** (files, rows, columns): Fine-grained authorization beyond "role may call server X". In `policy.yaml::resources`, define path grants (e.g., `["src/**", "docs/**"]`), column denies (e.g., `[salary]`), and row filters (e.g., `region: "$identity.region"`). Evaluated at Authorization stage; mismatches → 403 `resource_scope` (tool_call) or masked via `resource_projection` (tool_result).

3. **Workbench window** (`/admin/workbench`, `/api/workbench/trace`, `/api/workbench/resources`): A dashboard pane showing every feature working live. Users can trace a prompt through the real pipeline with optional "force judge" flag; see all stages, violations, ML probability + path, judge verdict, training samples; simulate tool calls and resource filtering; curate the training set and retrain the tree with live SSE progress. All traces are audited like normal calls (visible in feed/audit, counted in stats).

## Engineering Rules

**TDD:** Write the failing test first, then implementation. Tests prove the contract before code ships.

**SOLID + Clean Code:** Single responsibility, dependency injection, no god objects, additive contracts only.

**Additive contracts:** Frozen Pydantic models and Protocol ports after Phase 0. New fields → optional + default, never breaking existing code. `evaluators.get("type_name")` reads params with `.get` and defaults, not required fields.

**New rule types:** Need (1) type in correct set in `domain/policy/parser.py` (`_DLP_TYPES`, `_AUTHORIZATION_TYPES`, `_POLICY_TYPES`, or `_BEHAVIOR_TYPES`), (2) evaluator in `application/evaluators/{stage}/*.py`, (3) entry in `application/evaluators/__init__.py::build_evaluators`, (4) `EXPECTED_TYPES` in `tests/unit/application/evaluators/test_build_evaluators.py` and parametrized stage case in `tests/unit/domain/policy/test_parser.py`.

**No unnecessary comments:** No docstrings or comments restating the name or narrating the code; no section banners. A comment only explains a non-obvious why. Exception: `demo/mcp/*` tool docstrings are MCP tool descriptions (FastMCP exposes them) and must stay.

**Pytest:** Run without double `-q` (`pyproject.toml` already sets `-q`; `-qq` hides the summary line).

**Delivered content never changes silently:** When content is blocked or masked, the reason is logged and visible. Projection masking is reported as `Authorization · resource_projection, status MASKED`, not silent.

## Commands

```bash
# Bootstrap: installs Python 3.13 deps, Node modules, trains ML, pulls Ollama model
./scripts/bootstrap.ps1        # Windows
./scripts/bootstrap.sh         # Unix

# Run dev servers (Control Layer :8080, Demo Agent :8090, Dashboard :5173)
./scripts/run_dev.ps1

# Test suite (pytest, ruff, npm test + build + lint)
./scripts/test.ps1
# Or per-module:
cd Backend && python -m pytest -q && python -m ruff check src tests
cd Frontent && npm test -- --run && npm run build && npm run lint
# Note: MCP server logs may swallow the pytest summary line. Use `-o addopts=""` or a junit report if needed.

# Native run on free ports (8082/8092/5175, no Docker compose needed)
CTRL_PORT=8082 AGENT_PORT=8092 VITE_CONTROL_LAYER_URL=http://localhost:8082 AGENT_CONTROL_LAYER_URL=http://localhost:8082 npm run dev -- --port 5175

# Train ML classifier and decision tree
./scripts/train_ml.ps1

# Attack suite (68 scenarios: 19 positive, 49 negative)
python attack_suite.py --target http://localhost:8080
python attack_suite.py --target http://localhost:8081 --agent ollama
```

## Environment

**Docker + WSL:** Machine runs Docker Engine inside WSL2 (NAT), not Docker Desktop. `host.docker.internal` does not resolve. Ports 8080, 8090, 5173, 6379 are held by `docker-compose` via wslrelay. For native runs, use next available pair (8081, 8091) and set `CTRL_PORT=8081 AGENT_PORT=8091 VITE_CONTROL_LAYER_URL=http://localhost:8081 AGENT_CONTROL_LAYER_URL=http://localhost:8081`. Never kill wslrelay; if 8081/8091 busy, pick the next free pair.

**Ollama:** Native runs talk to `127.0.0.1:11434`. `OLLAMA_HOST=0.0.0.0` is only needed for Docker containers → Ollama on the host. `qwen2.5:7b` is pulled by bootstrap; mock provider is automatic fallback.

**ML artifacts:** Stored in `Backend/src/control_layer/ml/artifacts/` (`prompt_injection_tree.joblib`, `prompt_injection_classifier.joblib`, `.meta.json`); gitignored. Built by `scripts/bootstrap.ps1` and `scripts/train_ml.ps1`. Training samples: `Backend/data/judge_samples.jsonl` (gitignored). Tests train in-session or skip; artifact paths point to temp dirs via `conftest.py`.

**Check before run:** `GET /health` → inspect `provider.name` (`ollama` or `mock`) and `GET /api/protection` → inspect mode (`enforce`, `monitor`, or `off`).

## Team Org & Delegation

**Model levels:** Opus = senior, Sonnet = mid, Haiku = junior + one journalist.

**Fable (lead):** Design, integration briefs, final verification, all checkpoints, deployment.

**Opus (senior):** Architecture-sensitive backend (classifier, orchestration, judge, critical evaluators).

**Sonnet (mid):** Multi-file implementations (resource evaluators, pipeline fixes, Workbench API, integration tests).

**Haiku (junior):** Mechanical tasks (ML training, demo data, scripts, docs); one journalist collects hand-off notes, maintains CLAUDE.md/WIKI/team-journal.md.

**Subagent cap:** 12 per session. Each stream uses own worktree branch; lead merges.

**File ownership:** One owner per file per phase. Shared contracts (`policy.yaml`, `composition_root.py`, `conftest.py`, frozen domain models) are written once, then read-only. Each stream commits on its branch with explicit `git add <owned-files>` and submits hand-off note (decisions, gotchas, commands) to journalist.

## Definition of Done

✓ Backend suite green: `cd Backend; pytest -q; ruff check src tests`  
✓ Frontend green: `cd Frontent; npm test -- --run; npm run build; npm run lint`  
✓ Attack suite (68 scenarios): `python attack_suite.py --target <url>` → all pass  
✓ Docs complete: WIKI feature docs written, counts updated (README.md, feature docs, WIKI/demo-script.md, WIKI/judges-quickstart.md)  
✓ Hand-off notes written (decisions, gotchas, final commands per stream)  
✓ CLAUDE.md and WIKI/team-journal.md accurate  
✓ `git status` clean (only intended files committed)

---

**Team journal:** [WIKI/team-journal.md](WIKI/team-journal.md) — decision log and hand-off notes from all streams.
