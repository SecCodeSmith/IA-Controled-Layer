import { http, HttpResponse } from 'msw'
import { CONTROL_LAYER_URL, AGENT_URL, ADMIN_TOKEN } from '../api/client'
import { decodeMockToken, encodeMockToken } from './mockAuth'
import { workbenchHandlers } from './workbenchHandlers'
import {
  DEMO_USERS,
  toolsForServers,
  DEFAULT_BUDGET,
  POLICY_FIXTURE,
  FEED_FIXTURE,
  STATS_FIXTURE,
  ALERTS_FIXTURE,
  AUDIT_LIST_FIXTURE,
  CALL_DETAIL_FIXTURE,
  SCENARIOS_FIXTURE,
  SECURITY_REPORT_FIXTURE,
} from './fixtures'
import type { AgentChatResponse, AgentEvent } from '../types/chat'
import type { FeedRow } from '../types/feed'
import type { AttackRun, Scenario } from '../types/attack'
import type { ModelsResponse, ProtectionMode, ProtectionState } from '../types/protection'
import type { PolicyResponse, PolicyRule } from '../types/policy'

let callCounter = 1000
function nextCallId(): string {
  callCounter += 1
  return `c_${String(callCounter).padStart(6, '0')}`
}

interface PendingApproval {
  tool: string
  arguments: Record<string, unknown>
  ruleId: string
  reason: string
}

const state = {
  tokensUsed: DEFAULT_BUDGET.tokens_used,
  feed: [...FEED_FIXTURE] as FeedRow[],
  pendingApprovals: new Map<string, PendingApproval>(),
  approvalCounter: 0,
  attackRuns: new Map<string, AttackRun>(),
  attackRunCounter: 0,
  protectionMode: 'enforce' as ProtectionMode,
  ruleOverrides: {} as Record<string, boolean>,
  activeModel: { provider: 'ollama', model: 'qwen2.5:7b' },
  logsCleared: 0,
}

const DETERMINISTIC_SCENARIOS = ['spoofed_role_in_request', 'token_budget_overrun']

const AVAILABLE_MODELS: ModelsResponse['available'] = [
  { provider: 'ollama', model: 'qwen2.5:7b', allowed: true, size_gb: 4.7 },
  { provider: 'ollama', model: 'gemma4:latest', allowed: false, size_gb: 6.6 },
  { provider: 'mock', model: 'mock', allowed: true, size_gb: null },
]

function protectionState(): ProtectionState {
  return {
    mode: state.protectionMode,
    rule_overrides: { ...state.ruleOverrides },
    disabled_rules: Object.entries(state.ruleOverrides)
      .filter(([, enabled]) => !enabled)
      .map(([ruleId]) => ruleId),
  }
}

function policyWithOverrides(): PolicyResponse {
  const rulesByStage = Object.fromEntries(
    Object.entries(POLICY_FIXTURE.rules_by_stage).map(([stage, rules]) => [
      stage,
      (rules ?? []).map(
        (rule: PolicyRule): PolicyRule => ({
          ...rule,
          enabled: state.ruleOverrides[rule.id] ?? true,
          overridden: rule.id in state.ruleOverrides,
        }),
      ),
    ]),
  )
  return { ...POLICY_FIXTURE, rules_by_stage: rulesByStage }
}

export function resetMockState(): void {
  state.tokensUsed = DEFAULT_BUDGET.tokens_used
  state.feed = [...FEED_FIXTURE]
  state.pendingApprovals.clear()
  state.approvalCounter = 0
  state.attackRuns.clear()
  state.attackRunCounter = 0
  state.protectionMode = 'enforce'
  state.ruleOverrides = {}
  state.activeModel = { provider: 'ollama', model: 'qwen2.5:7b' }
  state.logsCleared = 0
}

function findUser(sub: string) {
  return DEMO_USERS.find((user) => user.sub === sub) ?? DEMO_USERS[0]
}

function buildAgentChatResponse(sessionId: string, message: string): AgentChatResponse {
  const normalized = message.toLowerCase()
  const events: AgentEvent[] = []

  if (normalized.includes('delete') && normalized.includes('branch')) {
    state.approvalCounter += 1
    const approvalId = `ap_${state.approvalCounter.toString(36).padStart(6, '0')}`
    state.pendingApprovals.set(approvalId, {
      tool: 'github.delete_branch',
      arguments: { repo: 'web-app', branch: 'feature/old-login' },
      ruleId: 'destructive_requires_approval',
      reason: 'Destructive actions need your confirmation',
    })
    events.push({
      type: 'approval_required',
      approval_id: approvalId,
      tool: 'github.delete_branch',
      arguments: { repo: 'web-app', branch: 'feature/old-login' },
      rule_id: 'destructive_requires_approval',
      reason: 'Destructive actions need your confirmation',
    })
    state.tokensUsed = Math.min(10000, state.tokensUsed + 60)
  } else if (normalized.includes('login') || (normalized.includes('hr') && normalized.includes('approv'))) {
    events.push(
      {
        type: 'tool_call',
        call_id: nextCallId(),
        tool: 'ci.get_run',
        arguments: { pipeline: 'e2e-login', date: '2026-10-02' },
        status: 'ALLOWED',
        stage: null,
        rule_id: null,
        reason: 'Matches roles.developer',
        items_masked: 0,
        result_preview: null,
      },
      {
        type: 'tool_call',
        call_id: nextCallId(),
        tool: 'logs-db.query',
        arguments: { service: 'auth', since: '24h' },
        status: 'MASKED',
        stage: 'dlp',
        rule_id: 'pii_masking',
        reason: '3 email addresses masked in the response',
        items_masked: 3,
        result_preview: '401 invalid_token user=[EMAIL_1]\n401 invalid_token user=[EMAIL_2]',
      },
      {
        type: 'tool_call',
        call_id: nextCallId(),
        tool: 'hr-db.find_approver',
        arguments: { request: 'test-accounts' },
        status: 'BLOCKED',
        stage: 'authorization',
        rule_id: 'role_provisioning',
        reason: 'HR database is not provisioned for the Developer role',
        items_masked: 0,
        result_preview: null,
      },
      {
        type: 'assistant_text',
        text:
          "The e2e-login run failed because the auth service rejected tokens for two test users after the key rotation at 02:10. I couldn't check the HR approver: that system isn't available to your role. You can ask HR directly or request access from your security admin.",
      },
    )
    state.tokensUsed = Math.min(10000, state.tokensUsed + 220)
  } else {
    events.push({
      type: 'assistant_text',
      text: "I looked into that and didn't find anything that needs escalation right now.",
    })
    state.tokensUsed = Math.min(10000, state.tokensUsed + 80)
  }

  return { session_id: sessionId, events, budget: { tokens_used: state.tokensUsed, tokens_limit: 10000 } }
}

export const handlers = [
  ...workbenchHandlers,
  http.get(`${CONTROL_LAYER_URL}/auth/users`, () => HttpResponse.json({ users: DEMO_USERS })),

  http.post(`${CONTROL_LAYER_URL}/auth/token`, async ({ request }) => {
    const body = (await request.json()) as { sub: string }
    const user = findUser(body.sub)
    const claims = {
      sub: user.sub,
      name: user.name,
      role: user.role,
      location: user.location,
      region: user.region,
      agent_id: `agent-${user.sub.split('.')[0]}-${user.role.slice(0, 3)}`,
      iss: 'control-layer-mock-sso',
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 28800,
    }
    return HttpResponse.json({
      access_token: encodeMockToken(claims),
      token_type: 'Bearer',
      expires_in: 28800,
      claims,
    })
  }),

  http.get(`${CONTROL_LAYER_URL}/v1/me`, ({ request }) => {
    const claims = decodeMockToken(request.headers.get('Authorization'))
    const user = findUser(claims?.sub ?? DEMO_USERS[0].sub)
    return HttpResponse.json({
      identity: {
        sub: user.sub,
        name: user.name,
        role: user.role,
        location: user.location,
        region: user.region,
        agent_id: claims?.agent_id ?? `agent-${user.sub.split('.')[0]}`,
      },
      tools: toolsForServers(user.mcp_servers),
      policy: { name: `roles.${user.role}`, version: POLICY_FIXTURE.version },
      budget: {
        tokens_used: state.tokensUsed,
        tokens_limit: DEFAULT_BUDGET.tokens_limit,
        cost_used_usd: DEFAULT_BUDGET.cost_used_usd,
        cost_limit_usd: DEFAULT_BUDGET.cost_limit_usd,
        resets_at: '2026-10-05T00:00:00Z',
      },
      risk: { score: 12, level: 'low' },
      provider: { name: 'ollama', model: 'qwen2.5:7b' },
      protection: { mode: state.protectionMode },
    })
  }),

  http.get(`${CONTROL_LAYER_URL}/v1/tools`, ({ request }) => {
    const claims = decodeMockToken(request.headers.get('Authorization'))
    const user = findUser(claims?.sub ?? DEMO_USERS[0].sub)
    return HttpResponse.json({ tools: toolsForServers(user.mcp_servers) })
  }),

  http.post(`${AGENT_URL}/agent/chat`, async ({ request }) => {
    const body = (await request.json()) as { session_id: string; message: string }
    return HttpResponse.json(buildAgentChatResponse(body.session_id, body.message))
  }),

  http.post(`${AGENT_URL}/agent/approvals/:approvalId`, async ({ request, params }) => {
    const approvalId = String(params.approvalId)
    const body = (await request.json()) as { session_id: string; decision: 'approve' | 'reject' }
    const pending = state.pendingApprovals.get(approvalId)
    state.pendingApprovals.delete(approvalId)

    const events: AgentEvent[] =
      body.decision === 'approve'
        ? [
            {
              type: 'tool_call',
              call_id: nextCallId(),
              tool: pending?.tool ?? 'github.delete_branch',
              arguments: pending?.arguments ?? {},
              status: 'ALLOWED',
              stage: null,
              rule_id: null,
              reason: 'Approved by user',
              items_masked: 0,
              result_preview: 'Branch feature/old-login deleted.',
            },
            { type: 'assistant_text', text: 'Done — the branch has been deleted.' },
          ]
        : [{ type: 'assistant_text', text: 'Understood, I will not delete the branch.' }]

    return HttpResponse.json({
      session_id: body.session_id,
      events,
      budget: { tokens_used: state.tokensUsed, tokens_limit: 10000 },
    })
  }),

  http.get(`${AGENT_URL}/agent/health`, () =>
    HttpResponse.json({
      status: 'ok',
      control_layer: CONTROL_LAYER_URL,
      provider: { name: 'ollama', model: 'qwen2.5:7b' },
    }),
  ),

  http.get(`${CONTROL_LAYER_URL}/api/feed`, ({ request }) => {
    if (request.headers.get('X-Admin-Token') !== ADMIN_TOKEN && !request.url.includes('admin_token=')) {
      return HttpResponse.json({ error: { code: 'identity_rejected', reason: 'Missing admin token' } }, { status: 401 })
    }
    return HttpResponse.json({ items: state.feed })
  }),

  http.get(`${CONTROL_LAYER_URL}/api/feed/stream`, () => {
    let interval: ReturnType<typeof setInterval> | undefined
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder()
        interval = setInterval(() => {
          const frame = `event: stats\ndata: ${JSON.stringify(STATS_FIXTURE)}\n\n`
          controller.enqueue(encoder.encode(frame))
        }, 15000)
        controller.enqueue(encoder.encode(': connected\n\n'))
      },
      cancel() {
        if (interval) clearInterval(interval)
      },
    })
    return new HttpResponse(stream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    })
  }),

  http.get(`${CONTROL_LAYER_URL}/api/audit`, () => HttpResponse.json({ items: AUDIT_LIST_FIXTURE })),

  http.get(`${CONTROL_LAYER_URL}/api/audit/:callId`, ({ params }) =>
    HttpResponse.json({ ...CALL_DETAIL_FIXTURE, call_id: String(params.callId) }),
  ),

  http.get(`${CONTROL_LAYER_URL}/api/audit/export`, () =>
    new HttpResponse('call_id,status\n', { headers: { 'Content-Type': 'text/csv' } }),
  ),

  http.get(`${CONTROL_LAYER_URL}/api/alerts`, () => HttpResponse.json({ items: ALERTS_FIXTURE })),

  http.get(`${CONTROL_LAYER_URL}/api/alerts/export`, () =>
    new HttpResponse(new Blob(), { headers: { 'Content-Type': 'application/vnd.ms-excel' } }),
  ),

  http.get(`${CONTROL_LAYER_URL}/api/stats`, () =>
    HttpResponse.json({ ...STATS_FIXTURE, protection: { mode: state.protectionMode } }),
  ),

  http.get(`${CONTROL_LAYER_URL}/api/policy`, () => HttpResponse.json(policyWithOverrides())),

  http.post(`${CONTROL_LAYER_URL}/api/policy/reload`, () => HttpResponse.json(policyWithOverrides())),

  http.get(`${CONTROL_LAYER_URL}/api/protection`, () => HttpResponse.json(protectionState())),

  http.put(`${CONTROL_LAYER_URL}/api/protection`, async ({ request }) => {
    const body = (await request.json()) as { mode: ProtectionMode }
    state.protectionMode = body.mode
    return HttpResponse.json(protectionState())
  }),

  http.delete(`${CONTROL_LAYER_URL}/api/protection/overrides`, () => {
    state.ruleOverrides = {}
    return HttpResponse.json(protectionState())
  }),

  http.patch(`${CONTROL_LAYER_URL}/api/policy/rules/:ruleId`, async ({ request, params }) => {
    const ruleId = String(params.ruleId)
    const known = Object.values(POLICY_FIXTURE.rules_by_stage).some((rules) =>
      (rules ?? []).some((rule) => rule.id === ruleId),
    )
    if (!known) {
      return HttpResponse.json({ error: { code: 'not_found', reason: 'Unknown rule' } }, { status: 404 })
    }
    const body = (await request.json()) as { enabled: boolean }
    state.ruleOverrides[ruleId] = body.enabled
    return HttpResponse.json({ rule_id: ruleId, enabled: body.enabled, overridden: true })
  }),

  http.get(`${CONTROL_LAYER_URL}/api/models`, () =>
    HttpResponse.json({
      active: { name: state.activeModel.provider, model: state.activeModel.model },
      available: AVAILABLE_MODELS,
    }),
  ),

  http.put(`${CONTROL_LAYER_URL}/api/models`, async ({ request }) => {
    const body = (await request.json()) as { provider: string; model: string }
    const exists = AVAILABLE_MODELS.some((m) => m.provider === body.provider && m.model === body.model)
    if (!exists) {
      return HttpResponse.json({ error: { code: 'not_found', reason: 'Model not available' } }, { status: 404 })
    }
    state.activeModel = body
    return HttpResponse.json({ name: body.provider, model: body.model })
  }),

  http.post(`${CONTROL_LAYER_URL}/api/logs/clear`, () => {
    state.logsCleared += 1
    state.feed = []
    return HttpResponse.json({
      ok: true,
      cleared: ['audit', 'alerts', 'alerts_xlsx', 'audit_jsonl', 'metrics', 'feed'],
    })
  }),

  http.get(`${CONTROL_LAYER_URL}/api/reports/security`, () => HttpResponse.json(SECURITY_REPORT_FIXTURE)),

  http.get(`${CONTROL_LAYER_URL}/api/attack-suite/scenarios`, () =>
    HttpResponse.json({
      scenarios: SCENARIOS_FIXTURE.map((scenario) => ({
        ...scenario,
        agent_driven: !DETERMINISTIC_SCENARIOS.includes(scenario.id),
      })),
    }),
  ),

  http.post(`${CONTROL_LAYER_URL}/api/attack-suite/run`, ({ request }) => {
    const url = new URL(request.url)
    const agent = (url.searchParams.get('agent') ?? 'scripted') as 'scripted' | 'ollama'
    state.attackRunCounter += 1
    const runId = `run_${state.attackRunCounter}`
    const scenarios: Scenario[] = SCENARIOS_FIXTURE.map((scenario) => ({
      ...scenario,
      agent_driven: !DETERMINISTIC_SCENARIOS.includes(scenario.id),
      via: null,
      status: 'PENDING',
      observed: null,
      duration_ms: null,
    }))
    const run: AttackRun = {
      run_id: runId,
      number: state.attackRunCounter,
      agent,
      provider: state.activeModel.provider,
      model: state.activeModel.model,
      protection_mode: state.protectionMode,
      started_at: new Date().toISOString(),
      scenarios,
      summary: { stopped: 0, passed: 0, succeeded: 0, not_attempted: 0, error: 0, running: 0, pending: scenarios.length },
    }
    state.attackRuns.set(runId, run)
    return HttpResponse.json(run)
  }),

  http.get(`${CONTROL_LAYER_URL}/api/attack-suite/runs/:runId`, ({ params }) => {
    const run = state.attackRuns.get(String(params.runId))
    if (!run) return HttpResponse.json({ error: { code: 'not_found', reason: 'Run not found' } }, { status: 404 })
    return HttpResponse.json(run)
  }),

  http.get(`${CONTROL_LAYER_URL}/api/attack-suite/runs/:runId/stream`, ({ params }) => {
    const run = state.attackRuns.get(String(params.runId))
    let timer: ReturnType<typeof setInterval> | undefined
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder()
        if (!run) {
          controller.close()
          return
        }
        let index = 0
        const summary = { stopped: 0, passed: 0, succeeded: 0, not_attempted: 0, error: 0, running: 0, pending: run.scenarios.length }
        timer = setInterval(() => {
          if (index >= run.scenarios.length) {
            if (timer) clearInterval(timer)
            controller.enqueue(encoder.encode(`event: run_complete\ndata: ${JSON.stringify({ summary })}\n\n`))
            controller.close()
            return
          }
          const scenario = run.scenarios[index]
          const finalStatus: 'STOPPED' | 'PASSED' = scenario.kind === 'negative' ? 'STOPPED' : 'PASSED'
          summary.pending -= 1
          if (finalStatus === 'STOPPED') summary.stopped += 1
          else summary.passed += 1
          const event = {
            id: scenario.id,
            status: finalStatus,
            observed: { status: scenario.expected.status, stage: scenario.stage, rule_id: scenario.expected.rule_id },
            duration_ms: 120 + index * 10,
            via: 'scripted',
          }
          controller.enqueue(encoder.encode(`event: scenario\ndata: ${JSON.stringify(event)}\n\n`))
          index += 1
        }, 700)
      },
      cancel() {
        if (timer) clearInterval(timer)
      },
    })
    return new HttpResponse(stream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    })
  }),

  http.post(`${CONTROL_LAYER_URL}/api/demo/reset`, () => {
    resetMockState()
    return HttpResponse.json({ ok: true })
  }),

  http.get(`${CONTROL_LAYER_URL}/health`, () =>
    HttpResponse.json({
      status: 'ok',
      stages: ['identity', 'authorization', 'dlp', 'policy', 'behavior', 'resource', 'audit'],
      cache: { mode: 'memory' },
      mcp: { servers: [] },
      classifier: { loaded: true, path: 'mock' },
      provider: { name: 'ollama', model: 'qwen2.5:7b' },
      policy: { version: POLICY_FIXTURE.version, status: POLICY_FIXTURE.status },
    }),
  ),
]
