# 6-Minute Presentation Demo Script

This script walks through the AI Control Layer demo for a 6-minute presentation or live demo. Timings are approximate.

## Setup (before presentation)

- Both terminals ready:
  - **Terminal A:** Control Layer + Demo Agent + Frontend running (`run_dev.ps1` / `run_dev.sh`)
  - **Terminal B:** Ready for `attack_suite.py --target http://localhost:8080`
- Four browser tabs open (but minimized):
  1. **http://localhost:8080/health** (Control Layer health)
  2. **http://localhost:5173** (Dashboard, signed in as Anna Kowalska)
  3. **http://localhost:5173/admin** (Live Feed)
  4. **http://localhost:5173/admin/policy** (Policy page)
- `Backend/config/policy.yaml` open in editor (side-by-side or ready to show)
- `Backend/alerts/alerts.xlsx` ready to open after demo

---

## Slide / Segment 1: Problem (1 min)

**What you say:**

> "AI agents are powerful but dangerous. They can:\
> • Make unauthorized tool calls (deleting data, sending emails)\
> • Leak sensitive information (customer PII, internal secrets)\
> • Be hijacked by prompt injection (attacker overrides goals)\
> • Exceed budgets and DoS the platform\
>  \
> Traditional firewalls don't understand agent intent. We need a smart, **policy-driven proxy** that sits between agent and backend, enforces role-based access, detects attacks in real time, and audits everything."

**What you show:**

- Problem summary slide (from deck)
- Mockup of three rejected calls (BLOCKED, MASKED, ESCALATED)

---

## Slide / Segment 2: Solution Overview (1 min)

**What you say:**

> "The AI Control Layer is a seven-stage pipeline:\
> 1. **Identity** — verify JWT, resolve user claims (role, location)\
> 2. **Authorization** — role-based tool access, destructive approval\
> 3. **DLP** — detect and mask PII, block exfiltration\
> 4. **Policy** — signature-based + ML + LLM-judge injection detection\
> 5. **Behavior** — rate limit, loop guard, anomaly flags\
> 6. **Resource** — token budgets, cost limits, timeouts\
> 7. **Audit** — log every call, emit alerts, export reports\
>  \
> Each stage can short-circuit; decisions are cached by role + policy version. Hot-reloadable YAML policy."

**What you show:**

- Architecture diagram slide (Mermaid flowchart)
- Component diagram showing agent → control layer → Ollama + MCP servers

---

## Segment 3: Live Demo — Chat (2 min)

**What you say:**

> "Let's see it in action. I'll sign in as Anna Kowalska, a developer in Poland with access to CI, GitHub, and logs—but not HR or Finance tools."

**Action:**

1. **Show Tab 2:** Dashboard at http://localhost:5173
   - If not signed in: click Anna Kowalska → gets JWT with `role: developer`, `location: Kraków, PL`
   - Budget header: **3,420 / 10,000 tokens** (live count)
   - Sidebar shows tools: `github`, `ci`, `logs-db`, `jira`

2. **Type chat prompt:**
   ```
   Why did the login tests fail last night? Check the CI run and the logs.
   ```

3. **Watch the response unfold** (agent calls tools):

   **Tool 1: ci.get_run**
   - Card appears: green badge "ALLOWED"
   - "Matches roles.developer"
   - Agent receives CI pipeline data

   **Tool 2: logs-db.query**
   - Card appears: orange badge "MASKED"
   - "DLP · pii_masking · 3 email addresses masked"
   - Agent receives log lines, but emails are `[EMAIL_1]`, `[EMAIL_2]`, `[EMAIL_3]`
   - Budget updates: **3,562 / 10,000** (added 142 tokens)

   **Tool 3: hr-db.find_approver** (should fail)
   - Card appears: red badge "BLOCKED"
   - "Authorization · role_provisioning"
   - "HR database is not provisioned for the Developer role"
   - No execution, no side effect

4. **Say while watching:**

   > "See? DLP automatically detects emails in logs and masks them before the agent sees them. The agent still gets useful information (timestamps, error codes), but can't exfiltrate the actual email addresses. And when it tries HR—a tool it doesn't have access to—the authorization stage blocks it immediately."

---

## Segment 4: Live Demo — Destructive Action Escalation (1 min)

**Type a second prompt:**

```
The feature/old-login branch is stale. Delete it from the web-app repo.
```

**Expected behavior:**

1. Agent calls `github.delete_branch`
2. Card appears: blue badge "ESCALATED"
3. "Authorization · destructive_requires_approval"
4. An **Approval Card** appears below with two buttons: **Approve** and **Reject**

**Say:**

> "Destructive actions—deletes, pushes to main, transfers—require human approval. The agent can't execute them automatically. Let me approve this one."

**Click Approve:**

1. Call executes immediately
2. Card becomes green "ALLOWED"
3. Budget updates
4. Agent gets response

**Contrast:** If you click Reject, the action is dropped; no side effect, fully audited.

---

## Segment 5: Live Demo — Admin Live Feed (30 sec)

**Show Tab 3:** http://localhost:5173/admin

**Say:**

> "The admin dashboard shows real-time KPIs and a live feed of all calls. See the counts: 3 total, 1 allowed, 1 masked, 1 blocked, 1 escalated. The table shows who called what, when, and what the control layer did. Filters let admins drill into specific users or rule violations."

**Optional: Click on a row** (e.g., the masked call) → **Call Detail** page.

Show:
- Raw response (includes actual email: `t.lis@example.com`)
- Delivered response (masked: `[EMAIL_1]`)
- Per-stage timing bar (DLP stage is slowest because of regex matching)

---

## Segment 6: Live Demo — Hot-Reload Policy (1 min)

**Say:**

> "The policy is centralized in YAML and hot-reloaded. Admins can change thresholds, add rules, or disable controls without restarting. Let me show you."

**Action:**

1. **Show Tab 4:** http://localhost:5173/admin/policy
   - Badge: "v3 LOADED"
   - Shows all rules grouped by stage

2. **In editor, edit** `Backend/config/policy.yaml`:
   - Find the `pii_masking` rule:
   ```yaml
   - id: pii_masking
     on: [response]
     detect: [email, phone, pesel, iban, pan]
     action: mask
   ```
   - Change `action: mask` to `action: block`
   - Save file

3. **Within ~1 second**, return to browser and refresh the Policy tab.
   - Badge now shows "v4 LOADED" (version auto-incremented)
   - Masking rule now says `action: block`

4. **Go back to Chat tab**. Send another message that would return emails (e.g., retry the logs query).
   - Instead of masking, it now shows: red "BLOCKED" – "DLP · pii_masking"
   - Call rejected with 403

5. **Revert the policy** (change `action: block` back to `action: mask`, save).
   - Within 1 second, badge → "v5 LOADED"
   - Next call works again (masked)

**Say:**

> "Live policy updates. No restart needed. The entire team—security, DevOps, compliance—can tweak controls in real time. Violations are immediately detected and reported."

---

## Segment 7: Attack Suite (1 min, optional if time allows)

**If time is tight, skip this.** If time permits:

**Show Tab 3 Admin panel**, or **open Terminal B**:

```bash
python attack_suite.py --target http://localhost:8080
```

**Say:**

> "We also have a comprehensive self-testing suite with 24 attack scenarios—5 positive cases (should be allowed), 19 negative cases (should be blocked at the right stage). Scenarios cover prompt injection, exfiltration, privilege escalation, budget overrun, and behavioral anomalies. Scripted tier runs in ~30 seconds with no model dependency. All green means the system is robust."

**Or:** If dashboard panel is visible, click **Run (Scripted)** and watch scenarios execute in real time (all 24 complete in under 1 minute).

---

## Segment 8: Audit and Reporting (30 sec)

**If time allows, show Tab 3** or open `Backend/alerts/alerts.xlsx`:

**Say:**

> "Every call is audited. Excel alerts file captures every violation in real time. JSONL audit log stores the full record for export: CSV, JSONL, or XLSX. Admins can drill into any call to see what matched, why, and what was masked before delivery. This evidence is critical for compliance, incident response, and threat hunting."

---

## Closing (30 sec)

**What you say:**

> "The AI Control Layer combines:\
> • **Deterministic rules** (signatures, RBAC, budgets) for speed and certainty\
> • **Machine learning** (Scikit-learn classifier) for subtle injection patterns\
> • **LLM judge** for edge cases and context-aware decisions\
> • **Real-time audit** for compliance and forensics\
> • **Hot-reload policy** so teams can respond to threats within seconds\
>  \
> It's OWASP-grounded, production-ready, and fully testable. Judges can clone the repo, run `bootstrap` and `run_dev`, and see all this in 5 minutes."

---

## Timing Reference

- **Segment 1 (Problem):** 1:00
- **Segment 2 (Architecture):** 1:00
- **Segment 3 (Chat demo):** 2:00
- **Segment 4 (Escalation):** 1:00
- **Segment 5 (Live feed):** 0:30
- **Segment 6 (Hot-reload):** 1:00
- **Segment 7 (Attack suite):** 0:30 (optional)
- **Segment 8 (Audit):** 0:30
- **Closing:** 0:30

**Total: ~8 minutes** (leaves buffer for questions and delays)

---

## Backup Plans

**If Ollama is slow / not available:**
- Policy and masking still demo fully with mock provider
- Skip "attack suite" tier that requires Ollama; focus on scripted tier
- Say: "In production, this runs on a local Ollama model (qwen2.5:7b) on RTX 4070, ~100ms overhead per call."

**If policy reload appears not to work:**
- File watcher polls every 1s; if edit wasn't detected, try saving again
- Refresh browser tab to verify version bump
- Worst case: manually restart control layer (`Ctrl+C` → `run_dev`), but keep chat history

**If a call times out or fails:**
- Redis might be disconnected; check `/health` endpoint
- Check terminal logs for error messages
- Proceed to next segment; don't dwell on technical glitches

---

**See also:** [Judges Quickstart](judges-quickstart.md), [Architecture](architecture.md)
