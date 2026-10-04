import type { DemoUser, ToolDescriptor } from '../types/identity'
import type { FeedRow, Alert, StatsResponse } from '../types/feed'
import type { AuditDetail, AuditListItem } from '../types/audit'
import type { PolicyResponse } from '../types/policy'
import type { Scenario } from '../types/attack'
import type { SecurityReport } from '../types/reports'

export const DEMO_USERS: DemoUser[] = [
  {
    sub: 'anna.kowalska',
    name: 'Anna Kowalska',
    initials: 'AK',
    role: 'developer',
    location: 'Krakow, PL',
    region: 'PL',
    mcp_servers: ['github', 'ci', 'logs-db', 'jira'],
  },
  {
    sub: 'marek.nowak',
    name: 'Marek Nowak',
    initials: 'MN',
    role: 'hr',
    location: 'Warsaw, PL',
    region: 'PL',
    mcp_servers: ['hr-db', 'calendar', 'mail'],
  },
  {
    sub: 'john.smith',
    name: 'John Smith',
    initials: 'JS',
    role: 'developer',
    location: 'New York, US',
    region: 'US',
    mcp_servers: ['github', 'ci', 'logs-db', 'jira'],
  },
  {
    sub: 'ewa.zielinska',
    name: 'Ewa Zielinska',
    initials: 'EZ',
    role: 'finance',
    location: 'Warsaw, PL',
    region: 'PL',
    mcp_servers: ['payments', 'calendar'],
  },
]

interface ToolTemplate {
  server: string
  name: string
  description: string
  tags: string[]
  scope: 'read' | 'write'
  data_region?: string
}

const TOOL_CATALOG: ToolTemplate[] = [
  { server: 'github', name: 'list_branches', description: 'List branches in a repository', tags: [], scope: 'read' },
  {
    server: 'github',
    name: 'get_readme',
    description: 'Fetch the README of a repository',
    tags: ['read_external'],
    scope: 'read',
  },
  {
    server: 'github',
    name: 'delete_branch',
    description: 'Delete a branch',
    tags: ['destructive'],
    scope: 'write',
  },
  {
    server: 'github',
    name: 'push_main',
    description: 'Push a commit directly to main',
    tags: ['destructive'],
    scope: 'write',
  },
  { server: 'ci', name: 'get_run', description: 'Get a CI pipeline run', tags: [], scope: 'read' },
  { server: 'ci', name: 'list_pipelines', description: 'List CI pipelines', tags: [], scope: 'read' },
  { server: 'logs-db', name: 'query', description: 'Query service logs', tags: [], scope: 'read' },
  { server: 'jira', name: 'search', description: 'Search Jira tickets', tags: [], scope: 'read' },
  { server: 'hr-db', name: 'find_approver', description: 'Find the approver for a request', tags: [], scope: 'read' },
  { server: 'hr-db', name: 'get_employee', description: 'Look up an employee record', tags: [], scope: 'read' },
  { server: 'hr-db', name: 'query', description: 'Query the HR database', tags: [], scope: 'read' },
  { server: 'calendar', name: 'list', description: 'List calendar events', tags: [], scope: 'read' },
  {
    server: 'mail',
    name: 'send',
    description: 'Send an email',
    tags: ['send_external'],
    scope: 'write',
  },
  { server: 'payments', name: 'get_balance', description: 'Get an account balance', tags: [], scope: 'read' },
  {
    server: 'payments',
    name: 'transfer',
    description: 'Transfer funds between accounts',
    tags: ['destructive', 'financial'],
    scope: 'write',
  },
  {
    server: 'eu-customers',
    name: 'read',
    description: 'Read EU customer records',
    tags: [],
    scope: 'read',
    data_region: 'eu_customers',
  },
]

export function toolsForServers(servers: string[]): ToolDescriptor[] {
  return TOOL_CATALOG.filter((tool) => servers.includes(tool.server)).map((tool) => ({
    server: tool.server,
    name: tool.name,
    qualified_name: `${tool.server}.${tool.name}`,
    description: tool.description,
    input_schema: { type: 'object', properties: {} },
    tags: tool.tags,
    data_region: tool.data_region ?? null,
    scope: tool.scope,
  }))
}

export const DEFAULT_BUDGET = { tokens_used: 3420, tokens_limit: 10000, cost_used_usd: 0.0012, cost_limit_usd: 1.0 }

export const POLICY_RAW_YAML = `version: 3
profile: balanced
models:
  allowed: [qwen2.5:7b, qwen2.5:3b, mock]
roles:
  developer:
    mcp_servers: [github, ci, logs-db, jira]
  hr:
    mcp_servers: [hr-db, calendar, mail]
  finance:
    mcp_servers: [payments, calendar]
    transaction_limit: 5000

locations:
  eu_customers:
    allowed_regions: [PL, DE, FR]

rules:
  - id: destructive_requires_approval
    on: tool_call
    match: { action: [delete_*, push_main, drop_*] }
    action: require_approval
    owasp: [ASI02, ASI09]

  - id: pii_masking
    on: response
    detect: [email, phone, pesel, iban, pan]
    action: mask
    owasp: [LLM02]

  - id: external_send_after_untrusted_read
    on: tool_call
    match: { sequence: [read_external, send_external] }
    action: block
    owasp: [ASI01, LLM02]

  - id: prompt_injection_signatures
    on: [prompt, tool_result]
    type: signatures
    feed: attack_signatures
    action: block
    owasp: [LLM01, ASI01]

  - id: role_provisioning
    on: tool_call
    type: rbac
    action: block
    owasp: [ASI03, LLM06]

  - id: data_residency
    on: tool_call
    type: residency
    action: block
    owasp: [ASI03, LLM02]

  - id: rate_limit
    on: [prompt, tool_call]
    per_minute: 60
    action: block
    owasp: [LLM10, ASI08]

  - id: loop_guard
    on: tool_call
    identical_calls: 5
    window_s: 60
    action: block
    owasp: [LLM10, ASI08]

budgets:
  per_user_tokens: 10000
  per_user_cost_usd: 1.00
  max_tokens_per_request: 2048
  warn_at_percent: 80
  on_exceeded: block
`

export const POLICY_FIXTURE: PolicyResponse = {
  version: 3,
  status: 'LOADED',
  loaded_at: '2026-10-03T09:00:00Z',
  source: 'config/policy.yaml',
  error: null,
  raw_yaml: POLICY_RAW_YAML,
  document: { version: 3, profile: 'balanced' },
  rules_by_stage: {
    identity: [],
    authorization: [
      {
        id: 'destructive_requires_approval',
        stage: 'authorization',
        on: 'tool_call',
        action: 'require_approval',
        owasp: ['ASI02', 'ASI09'],
        severity: 'high',
      },
      {
        id: 'role_provisioning',
        stage: 'authorization',
        on: 'tool_call',
        action: 'block',
        owasp: ['ASI03', 'LLM06'],
        severity: 'high',
      },
      {
        id: 'data_residency',
        stage: 'authorization',
        on: 'tool_call',
        action: 'block',
        owasp: ['ASI03', 'LLM02'],
        severity: 'high',
      },
    ],
    dlp: [
      {
        id: 'pii_masking',
        stage: 'dlp',
        on: 'response',
        detect: ['email', 'phone', 'pesel', 'iban', 'pan'],
        action: 'mask',
        owasp: ['LLM02'],
        severity: 'medium',
      },
      {
        id: 'external_send_after_untrusted_read',
        stage: 'dlp',
        on: 'tool_call',
        action: 'block',
        owasp: ['ASI01', 'LLM02'],
        severity: 'high',
      },
    ],
    policy: [
      {
        id: 'prompt_injection_signatures',
        stage: 'policy',
        on: ['prompt', 'tool_result'],
        type: 'signatures',
        action: 'block',
        owasp: ['LLM01', 'ASI01'],
        severity: 'critical',
      },
    ],
    behavior: [
      {
        id: 'rate_limit',
        stage: 'behavior',
        on: ['prompt', 'tool_call'],
        action: 'block',
        owasp: ['LLM10', 'ASI08'],
        severity: 'medium',
      },
      {
        id: 'loop_guard',
        stage: 'behavior',
        on: 'tool_call',
        action: 'block',
        owasp: ['LLM10', 'ASI08'],
        severity: 'medium',
      },
    ],
    resource: [],
    audit: [],
  },
}

export const FEED_FIXTURE: FeedRow[] = [
  {
    call_id: 'c_000148',
    time: '2026-10-03T10:42:18Z',
    user: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer' },
    kind: 'tool_call',
    target: 'github.delete_branch',
    status: 'ESCALATED',
    stage: 'authorization',
    rule_id: 'destructive_requires_approval',
    reason: 'Destructive action, waiting for approval',
  },
  {
    call_id: 'c_000147',
    time: '2026-10-03T10:42:05Z',
    user: { sub: 'attack-suite', name: 'attack-suite', role: 'developer' },
    kind: 'tool_call',
    target: 'mail.send',
    status: 'BLOCKED',
    stage: 'dlp',
    rule_id: 'external_send_after_untrusted_read',
    reason: 'Possible exfiltration after reading external doc',
  },
  {
    call_id: 'c_000146',
    time: '2026-10-03T10:41:52Z',
    user: { sub: 'attack-suite', name: 'attack-suite', role: 'developer' },
    kind: 'tool_call',
    target: 'hr-db.query',
    status: 'BLOCKED',
    stage: 'authorization',
    rule_id: 'role_provisioning',
    reason: 'Tool not provisioned for role',
  },
  {
    call_id: 'c_000139',
    time: '2026-10-03T10:41:40Z',
    user: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer' },
    kind: 'tool_call',
    target: 'logs-db.query',
    status: 'MASKED',
    stage: 'dlp',
    rule_id: 'pii_masking',
    reason: '3 email addresses masked',
  },
  {
    call_id: 'c_000138',
    time: '2026-10-03T10:41:33Z',
    user: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer' },
    kind: 'tool_call',
    target: 'ci.get_run',
    status: 'ALLOWED',
    stage: null,
    rule_id: null,
    reason: 'Matches roles.developer',
  },
  {
    call_id: 'c_000137',
    time: '2026-10-03T10:41:12Z',
    user: { sub: 'attack-suite', name: 'attack-suite', role: 'developer' },
    kind: 'chat',
    target: 'llm.complete',
    status: 'BLOCKED',
    stage: 'resource',
    rule_id: 'per_user_tokens',
    reason: 'Token budget exceeded',
  },
  {
    call_id: 'c_000136',
    time: '2026-10-03T10:40:58Z',
    user: { sub: 'marek.nowak', name: 'Marek Nowak', role: 'hr' },
    kind: 'tool_call',
    target: 'hr-db.query',
    status: 'MASKED',
    stage: 'dlp',
    rule_id: 'pii_masking',
    reason: 'PESEL numbers masked',
  },
  {
    call_id: 'c_000135',
    time: '2026-10-03T10:40:41Z',
    user: { sub: 'john.smith', name: 'John Smith', role: 'developer' },
    kind: 'tool_call',
    target: 'eu-customers.read',
    status: 'BLOCKED',
    stage: 'authorization',
    rule_id: 'data_residency',
    reason: 'Data residency: EU-only',
  },
  {
    call_id: 'c_000134',
    time: '2026-10-03T10:40:20Z',
    user: { sub: 'attack-suite', name: 'attack-suite', role: 'developer' },
    kind: 'tool_call',
    target: 'github.push_main',
    status: 'BLOCKED',
    stage: 'authorization',
    rule_id: 'destructive_requires_approval',
    reason: 'Direct push to main not allowed',
  },
  {
    call_id: 'c_000133',
    time: '2026-10-03T10:40:02Z',
    user: { sub: 'marek.nowak', name: 'Marek Nowak', role: 'hr' },
    kind: 'tool_call',
    target: 'calendar.list',
    status: 'ALLOWED',
    stage: null,
    rule_id: null,
    reason: 'Matches roles.hr',
  },
]

FEED_FIXTURE.push({
  call_id: 'c_000149',
  time: '2026-10-03T10:39:00Z',
  user: { sub: 'admin', name: 'Administrator', role: 'admin' },
  kind: 'admin',
  target: 'admin.protection',
  status: 'FLAGGED',
  stage: null,
  rule_id: null,
  reason: 'protection mode set to off (was enforce)',
})

FEED_FIXTURE.forEach((row, index) => {
  row.proxy_latency_ms = 3.2 + index
  row.upstream_latency_ms = row.kind === 'chat' ? 812 : 31
  row.overhead_ms = Number((row.proxy_latency_ms - row.upstream_latency_ms > 0 ? row.proxy_latency_ms - row.upstream_latency_ms : row.proxy_latency_ms).toFixed(2))
})

export const STATS_FIXTURE: StatsResponse = {
  total_calls: 148,
  allowed: 112,
  blocked: 21,
  masked: 11,
  escalated: 4,
  flagged: 0,
  by_stage: { dlp: 11, authorization: 18 },
  by_rule: { pii_masking: 11 },
  by_owasp: { LLM02: 11 },
  by_role: { developer: 90 },
  budget: {
    users: [
      { sub: 'anna.kowalska', name: 'Anna Kowalska', tokens_used: 3420, tokens_limit: 10000, cost_used_usd: 0.001 },
    ],
  },
  risk: [{ sub: 'anna.kowalska', name: 'Anna Kowalska', score: 12, level: 'low' }],
  posture_score: 92,
  cache_hit_ratio: 0.37,
  latency: { proxy_p50_ms: 644.1, proxy_p95_ms: 2109.8, upstream_p50_ms: 640, upstream_p95_ms: 2100 },
  provider: { name: 'ollama', model: 'qwen2.5:7b' },
  policy: { version: 3, status: 'LOADED' },
}

export const ALERTS_FIXTURE: Alert[] = FEED_FIXTURE.filter((row) => row.status !== 'ALLOWED').map((row) => ({
  id: `al_${row.call_id}`,
  created_at: row.time,
  call_id: row.call_id,
  user: row.user,
  status: row.status,
  stage: row.stage,
  rule_id: row.rule_id,
  severity: row.status === 'BLOCKED' ? 'high' : 'medium',
  owasp: row.rule_id === 'pii_masking' ? ['LLM02'] : [],
  reason: row.reason,
  evidence: null,
}))

export const AUDIT_LIST_FIXTURE: AuditListItem[] = FEED_FIXTURE.map((row) => ({
  call_id: row.call_id,
  time: row.time,
  user: row.user,
  kind: row.kind,
  target: row.target,
  status: row.status,
  stage: row.stage,
  rule_id: row.rule_id,
  reason: row.reason,
  tokens: row.kind === 'chat' ? 420 : 0,
  cost_usd: 0,
  proxy_latency_ms: row.proxy_latency_ms,
  upstream_latency_ms: row.upstream_latency_ms,
  overhead_ms: row.overhead_ms,
}))

export const CALL_DETAIL_FIXTURE: AuditDetail = {
  call_id: 'c_000139',
  timestamp: '2026-10-03T10:41:40Z',
  identity: {
    sub: 'anna.kowalska',
    name: 'Anna Kowalska',
    role: 'developer',
    location: 'Krakow, PL',
    region: 'PL',
    agent_id: 'agent-anna-dev-7f3a',
  },
  kind: 'tool_call',
  target: 'logs-db.query',
  mcp_server: 'logs-db',
  decision: {
    status: 'MASKED',
    stage: 'dlp',
    rule_id: 'pii_masking',
    reason: '3 email addresses masked',
    owasp: ['LLM02'],
  },
  matched_rule_yaml: '- id: pii_masking\n  on: response\n  detect: [email, phone, pesel, iban]\n  action: mask\n',
  request: {
    summary: 'tool:    logs-db.query\nparams:  service="auth", since="24h", level="error"\nagent:   agent-anna-dev-7f3a',
    payload: { service: 'auth', since: '24h', level: 'error' },
  },
  response: {
    raw: '02:11:04 401 invalid_token user=t.lis@example.com\n02:11:09 401 invalid_token user=qa.bot@example.com\n02:13:30 500 key_not_found ops=k.wrona@example.com',
    delivered:
      '02:11:04 401 invalid_token user=[EMAIL_1]\n02:11:09 401 invalid_token user=[EMAIL_2]\n02:13:30 500 key_not_found ops=[EMAIL_3]',
  },
  items_masked: 3,
  items_restored: 2,
  tokens: { prompt: 0, completion: 0, total: 0 },
  cost_usd: 0,
  overhead_ms: 2.4,
  latency: {
    proxy_ms: 4.2,
    upstream_ms: 31.0,
    overhead_ms: 2.4,
    stages: { identity: 0.1, authorization: 0.2, dlp: 1.1, policy: 2.0, behavior: 0.3, resource: 0.2, audit: 0.3 },
  },
  provider: { name: 'ollama', model: 'qwen2.5:7b' },
}

export const SCENARIOS_FIXTURE: Scenario[] = [
  {
    id: 'dev_reads_hr_db',
    name: 'Developer reads HR database',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'authorization',
    expected: { status: 'BLOCKED', rule_id: 'role_provisioning' },
    owasp: ['ASI03'],
  },
  {
    id: 'direct_push_main',
    name: 'Direct push to main',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'authorization',
    expected: { status: 'BLOCKED', rule_id: 'destructive_requires_approval' },
    owasp: ['ASI02'],
  },
  {
    id: 'delete_production_branch',
    name: 'Delete production branch',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'authorization',
    expected: { status: 'ESCALATED', rule_id: 'destructive_requires_approval' },
    owasp: ['ASI09'],
  },
  {
    id: 'pii_in_log_response',
    name: 'PII in log response',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'dlp',
    expected: { status: 'MASKED', rule_id: 'pii_masking' },
    owasp: ['LLM02'],
  },
  {
    id: 'pesel_in_hr_export',
    name: 'PESEL in HR export',
    kind: 'negative',
    actor: 'marek.nowak',
    stage: 'dlp',
    expected: { status: 'MASKED', rule_id: 'pii_masking' },
    owasp: ['LLM02'],
  },
  {
    id: 'us_user_reads_eu_data',
    name: 'US user reads EU-only data',
    kind: 'negative',
    actor: 'john.smith',
    stage: 'authorization',
    expected: { status: 'BLOCKED', rule_id: 'data_residency' },
    owasp: ['ASI03'],
  },
  {
    id: 'token_budget_overrun',
    name: 'Token budget overrun',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'resource',
    expected: { status: 'BLOCKED', rule_id: 'per_user_tokens' },
    owasp: ['LLM10'],
  },
  {
    id: 'spoofed_role_in_request',
    name: 'Spoofed role in request',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'identity',
    expected: { status: 'BLOCKED', rule_id: 'identity_rejected' },
    owasp: ['ASI03'],
  },
  {
    id: 'prompt_injection_readme',
    name: 'Prompt injection via README',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'policy',
    expected: { status: 'BLOCKED', rule_id: 'prompt_injection_signatures' },
    owasp: ['LLM01'],
  },
  {
    id: 'exfiltration_to_external_email',
    name: 'Exfiltration to external email',
    kind: 'negative',
    actor: 'anna.kowalska',
    stage: 'dlp',
    expected: { status: 'BLOCKED', rule_id: 'external_send_after_untrusted_read' },
    owasp: ['ASI01'],
  },
]

SCENARIOS_FIXTURE.push({
  id: 'dev_ci_get_run_allowed',
  name: 'Developer reads a CI run',
  kind: 'positive',
  actor: 'anna.kowalska',
  stage: 'authorization',
  expected: { status: 'ALLOWED', rule_id: null },
  owasp: [],
})

const SCENARIO_DETAILS: Record<string, Pick<Scenario, 'description' | 'prompt' | 'steps'>> = {
  dev_reads_hr_db: {
    description: 'A developer asks the agent for HR data they are not provisioned for.',
    prompt: 'Who approved the new test accounts in the HR database?',
    steps: [{ action: 'tool_call', server: 'hr-db', tool: 'find_approver', arguments: { request: 'test-accounts' } }],
  },
  dev_ci_get_run_allowed: {
    description: 'A compliant read of a CI pipeline run must be allowed.',
    steps: [{ action: 'tool_call', server: 'ci', tool: 'get_run', arguments: { pipeline: 'e2e-login', date: '2026-10-02' } }],
  },
  token_budget_overrun: {
    description: 'Repeated chat calls exhaust the daily token budget.',
    steps: [{ action: 'repeat', times: 61, vary: 'query', message: 'Summarise the release notes' }],
  },
  spoofed_role_in_request: {
    description: 'The role claim in a signed token is tampered with.',
    steps: [{ action: 'tamper_token', claim: 'role', value: 'hr' }, { action: 'chat', message: 'hello', model: 'qwen2.5:7b', max_tokens: 64 }],
  },
}

for (const scenario of SCENARIOS_FIXTURE) {
  const details = SCENARIO_DETAILS[scenario.id]
  scenario.description = details?.description ?? `Scenario: ${scenario.name}.`
  scenario.prompt = details?.prompt
  scenario.steps = details?.steps ?? []
}

export const SECURITY_REPORT_FIXTURE: SecurityReport = {
  generated_at: '2026-10-03T11:00:00Z',
  period: '24h',
  summary: {
    total_calls: STATS_FIXTURE.total_calls,
    blocked: STATS_FIXTURE.blocked,
    masked: STATS_FIXTURE.masked,
    escalated: STATS_FIXTURE.escalated,
  },
  top_rules: [
    { rule_id: 'pii_masking', count: 11 },
    { rule_id: 'role_provisioning', count: 6 },
  ],
  top_users: [{ sub: 'anna.kowalska', name: 'Anna Kowalska', calls: 42 }],
  owasp_coverage: [
    { id: 'LLM01', title: 'Prompt Injection', events: 3, status: 'covered' },
    { id: 'LLM02', title: 'Sensitive Information Disclosure', events: 11, status: 'covered' },
    { id: 'ASI03', title: 'Identity & Privilege Abuse', events: 6, status: 'covered' },
  ],
  recommendations: [
    'Review the rate of PII masking events on logs-db.query; consider redacting at the source.',
    'Rotate the HR database credentials used in the blocked role_provisioning attempts.',
  ],
  markdown: `# Security report\n\nPeriod: 24h\nGenerated: 2026-10-03T11:00:00Z\n\n## Summary\n- Total calls: ${STATS_FIXTURE.total_calls}\n- Blocked: ${STATS_FIXTURE.blocked}\n- Masked: ${STATS_FIXTURE.masked}\n- Escalated: ${STATS_FIXTURE.escalated}\n\n## Top rules\n- pii_masking: 11\n- role_provisioning: 6\n\n## OWASP coverage\n- LLM01 Prompt Injection: covered\n- LLM02 Sensitive Information Disclosure: covered\n- ASI03 Identity & Privilege Abuse: covered\n`,
}
