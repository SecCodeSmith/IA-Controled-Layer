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

**Seven-stage order** (validated at startup, frozen in `application/pipeline/stages/`): Identity → Authorization → DLP → Policy → Behavior → Resource → Audit. Stages 1, 2, 6, 7 always run. Stages 3–4 cacheable.

**Rule type → evaluator:** Each rule in `policy.yaml` has a `type` field (e.g., `jwt_verify`, `role_provisioning`, `pii_masking`, `signature`, `ml_classifier`, `decision_tree`, `resource_scope`, `resource_projection`, `rate_limit`). The `domain/policy/parser.py::_RULE_TYPE_STAGES` dict maps type → stage. The `application/evaluators/build_evaluators()` function instantiates the right evaluator class per type and stage.

**Interception points:** `prompt` (agent text), `response` (model output), `tool_call` (agent → tool), `tool_result` (tool → agent). Each rule's `on: [...]` declares which points apply.

**Decision cache:** `ProcessingPipeline._build_cache_key()` runs before DLP/Policy stages, keyed on `(role, policy_version, context_text_hash)`. Cache stores full `DLP + Policy` bundle (`masked_text`, violations). **Must be fixed for resource projection:** key computed lazily from `post-authorization current_text + resolved role` (not `anonymous` pre-auth text), so user B cannot see user A's projected rows from cache.

**Hot-reload:** `config/policy.yaml` watched every 1 s. Valid YAML → version bumps, cache clears, new rules active. Invalid → ERROR badge, last good kept, alert emitted. No restart needed.

## Three New Features (In Progress 2026-10-04)

1. **Decision-tree feedback loop** (`/api/classifier`, `/admin/workbench`): A Scikit-learn decision tree (depth 12, min-leaf 2, F1 ≥0.85) runs alongside the existing logreg rule; positive verdicts are randomly sampled and re-evaluated by the LLM judge (judge verdict is final); the judge's verdicts are recorded as labelled samples and curated by a "training-set curator" prompt; accepted samples retrain the tree, which is hot-swapped without restart. Prevents benign false positives (e.g., "Delete the stale branch") from turning FLAGGED. Tree positive + judge allow → ALLOWED + label-0 sample recorded for future learning.

2. **Resource scope** (files, rows, columns): Fine-grained authorization beyond "role may call server X". In `policy.yaml::resources`, define path grants (e.g., `["src/**", "docs/**"]`), column denies (e.g., `[salary]`), and row filters (e.g., `region: "$identity.region"`). Evaluated at Authorization stage; mismatches → 403 `resource_scope` (tool_call) or masked via `resource_projection` (tool_result).

3. **Workbench window** (`/admin/workbench`, `/api/workbench/trace`, `/api/workbench/resources`): A dashboard pane showing every feature working live. Users can trace a prompt through the real pipeline with optional "force judge" flag; see all stages, violations, ML probability + path, judge verdict, training samples; simulate tool calls and resource filtering; curate the training set and retrain the tree with live SSE progress. All traces are audited like normal calls (visible in feed/audit, counted in stats).

## Engineering Rules

**TDD:** Write the failing test first, then implementation. Tests prove the contract before code ships.

**SOLID + Clean Code:** Single responsibility, dependency injection, no god objects, additive contracts only.

**Additive contracts:** Frozen Pydantic models and Protocol ports after Phase 0. New fields → optional + default, never breaking existing code. `evaluators.get("type_name")` reads params with `.get` and defaults, not required fields.

**New rule types:** Need (1) parser entry in `domain/policy/parser.py::_RULE_TYPE_STAGES`, (2) evaluator in `application/evaluators/{stage}/*.py`, (3) factory call in `build_evaluators()`, (4) EXPECTED_TYPES assertion in `tests/unit/domain/policy/test_parser.py:36-61`.

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

# Train ML classifier and decision tree
./scripts/train_ml.ps1

# Attack suite (27 scenarios: 6 positive, 21 negative)
python attack_suite.py --target http://localhost:8080
python attack_suite.py --target http://localhost:8081 --agent ollama
```

## Environment Gotchas

**Ports held by docker-compose:** On this machine (WSL + Docker Desktop), ports 8080, 8090, 5173, 6379 are held by `docker-compose` services. For native runs, use 8081, 8091, 5174 and set:
```
VITE_CONTROL_LAYER_URL=http://localhost:8081
AGENT_CONTROL_LAYER_URL=http://localhost:8081
CTRL_PORT=8081
AGENT_PORT=8091
```

**Ollama:** Native `.env` must use `CTRL_OLLAMA_BASE_URL=http://localhost:11434` (not `host.docker.internal`). On Windows, ensure Ollama listens on `0.0.0.0:11434` (set `OLLAMA_HOST=0.0.0.0:11434` and restart tray app).

**Model:** `qwen2.5:7b` (pulled by bootstrap). Mock provider is automatic fallback.

**ML artifacts:** `*.joblib` files under `Backend/ml/artifacts/` are gitignored. Built by `scripts/bootstrap.ps1` and `scripts/train_ml.ps1`. Tests train in-session or skip; `tests/conftest.py::make_settings` points artifact paths to temp directories. Worktrees running pytest must use `PYTHONPATH=src` because the package is installed editable from the main checkout.

**Check before judging a run:** POST `/health` and inspect `provider` (should be `ollama` or `mock`, not `error`) and `protection_mode` (should be `enforce` or `warn`, not `off`).

## Team Org & Delegation

**Fable (lead):** Design, architecture decisions, integration briefs, final verification, full test suite, all checkpoints, deployment.

**Opus (senior Opus worker, if present):** Architecture-sensitive backend (F1 classifier logic, stage orchestration, judge integration, critical evaluators). Owns file-sharing contracts with other streams.

**Sonnet (mid):** Multi-file implementations (F2 resource evaluators + pipeline fixes, F3 Workbench API + frontend, both tiers of integration tests).

**Haiku (junior):** Mechanical, well-bounded tasks (ML training + adapters, demo data, scripts, docs). One Haiku journalist collects hand-off notes and maintains CLAUDE.md, WIKI, team journal.

**File ownership (per stream, per phase):** One owner per file per phase. Shared contracts (`policy.yaml`, `composition_root.py`, `conftest.py`, frozen domain models) are written and reviewed once, then read-only for other streams. Each stream commits on its own branch with explicit `git add <owned-files>` and reports raw test output + diff stats + a hand-off note (decisions, gotchas, commands) for the journalist.

## Definition of Done

✓ Backend suite green: `cd Backend; pytest -q; ruff check src tests`  
✓ Frontend green: `cd Frontent; npm test -- --run; npm run build; npm run lint`  
✓ Attack suite (27 scenarios): `python attack_suite.py --target <url>` → all pass  
✓ Docs complete: WIKI feature docs written, counts updated (README.md, feature docs, WIKI/demo-script.md, WIKI/judges-quickstart.md)  
✓ Hand-off notes written (decisions, gotchas, final commands per stream)  
✓ CLAUDE.md and WIKI/team-journal.md accurate  
✓ `git status` clean (only intended files committed)

---

**Team journal:** [WIKI/team-journal.md](WIKI/team-journal.md) — decision log and hand-off notes from all streams.
