# WIKI — AI Control Layer Documentation

This directory contains the complete documentation for the AI Control Layer project.

## Quick Navigation

### For Judges and Newcomers
- **[Judges Quickstart](judges-quickstart.md)** — 10-minute getting-started guide. Start here.
- **[Demo Script](demo-script.md)** — 6-minute live demo walkthrough with talking points.

### For Engineers (Development Guide)
- **[CLAUDE.md](../CLAUDE.md)** — Development guide: architecture rules, engineering practices, commands, team org, environment setup.
- **[Team Journal](team-journal.md)** — Decision log, hand-off notes, verified facts, risk mitigations, phase checkpoints.

### For Understanding the System
- **[Architecture](architecture.md)** — Component diagram, seven-stage pipeline, Mermaid diagrams, directory structure.
- **[API Contract](api-contract.md)** — Full API specification: endpoints, request/response shapes, authentication, error codes.
- **[Policy Reference](policy-reference.md)** — Complete `policy.yaml` structure, rule types, hot-reload mechanism, worked examples.

### For Security and Compliance
- **[OWASP Mapping](owasp-mapping.md)** — Coverage table for LLM Top 10 2025 and Agentic Top 10 2026, with demo scenario proof for each threat.

### Reference Files
- **[reference/task.req](reference/task.req)** — Original HackYeah challenge requirements.
- **[reference/ui-mockups.html](reference/ui-mockups.html)** — Mockups of the five dashboard screens.

---

## Core Concepts

### Seven-Stage Pipeline

Every call flows through a fixed, ordered chain:

1. **Identity** — Verify JWT, resolve user claims → 401 if tampered
2. **Authorization** — RBAC, residency, approval gates → 403 if denied
3. **DLP** — PII/secrets detection and masking → 403 or masked forward
4. **Policy** — Injection signatures, ML, LLM judge → 403 or escalate
5. **Behavior** — Rate limit, loop guard, circuit breaker → 429 or quarantine
6. **Resource** — Token budgets, cost limits, timeouts → 403 if exceeded
7. **Audit** — Logging, alerting, metrics → always

Stages 1, 2, 6, 7 always run. Stages 3–4 (DLP, Policy) are cacheable.

### Hot-Reloadable Policy

- **Location:** `config/policy.yaml`
- **Reload:** File watcher polls every 1 second; valid changes bump version and clear cache
- **Invalid YAML:** Keeps last good policy, emits alert, shows ERROR badge
- **No restart needed:** Teams can adjust thresholds, enable/disable rules in real time

### Three-Tier Defence

1. **Deterministic rules** (RBAC, budgets, signatures) — Fast, certain
2. **ML classifier** (Scikit-learn) — Detects subtle injection patterns
3. **LLM judge** (Ollama) — Context-aware decisions for edge cases

### OWASP Grounded

- **LLM Top 10 2025:** Covers all 10 threats (excepting out-of-scope LLM08, LLM09 partial)
- **Agentic Top 10 2026:** Covers all 10 threats (excepting out-of-scope ASI07)
- Evidence: [OWASP Mapping](owasp-mapping.md)

---

## Getting Started

### Prerequisites

- Python 3.13+
- Node 24+
- Ollama (optional; mock fallback included)

### Quickstart (5 minutes)

```bash
# Clone and enter repo
cd IA-Controled-Layer

# Bootstrap (installs deps, trains ML, pulls model)
./scripts/bootstrap.sh   # or .ps1 on Windows

# Start dev servers
./scripts/run_dev.sh     # or .ps1

# Open dashboard
open http://localhost:5173
# Sign in as Anna Kowalska (Developer, Kraków)

# Run self-testing suite
python attack_suite.py --target http://localhost:8080
```

For full walkthrough, see **[Judges Quickstart](judges-quickstart.md)**.

---

## Testing

### Unit + Integration Tests

```bash
cd Backend
python -m pytest -q --cov=control_layer --cov-report=term-missing
```

### Attack Suite

```bash
# Scripted tier (deterministic, mock provider)
python attack_suite.py --target http://localhost:8080

# Ollama tier (real agent + model)
python attack_suite.py --target http://localhost:8080 --agent ollama
```

---

## Key Readings

1. **[Judges Quickstart](judges-quickstart.md)** — Start here if new
2. **[Architecture](architecture.md)** — Understand the design
3. **[Policy Reference](policy-reference.md)** — Learn to configure
4. **[OWASP Mapping](owasp-mapping.md)** — Security posture
5. **[Demo Script](demo-script.md)** — Presentation walkthrough

---

## Questions?

- **Getting started?** → [Judges Quickstart](judges-quickstart.md)
- **How does it work?** → [Architecture](architecture.md)
- **How do I configure it?** → [Policy Reference](policy-reference.md)
- **Is it secure?** → [OWASP Mapping](owasp-mapping.md)
- **How do I present it?** → [Demo Script](demo-script.md)
- **API details?** → [API Contract](api-contract.md)

---

**Last updated:** 2026-10-03 | **Project:** AI Control Layer | **Challenge:** HackYeah 2026
