import type { CallKind, FeedUser } from './feed'
import type { CallStatus, PipelineStage } from './common'

export interface AuditListItem {
  call_id: string
  time: string
  user: FeedUser
  kind: CallKind
  target: string
  status: CallStatus
  stage: PipelineStage | null
  rule_id: string | null
  reason: string
  tokens?: number
  cost_usd?: number
  proxy_latency_ms?: number | null
  upstream_latency_ms?: number | null
  overhead_ms?: number | null
}

export interface AuditListResponse {
  items: AuditListItem[]
}

export interface AuditIdentity {
  sub: string
  name: string
  role: string
  location: string
  region: string
  agent_id: string
}

export interface AuditDecision {
  status: CallStatus
  stage: PipelineStage | null
  rule_id: string | null
  reason: string
  owasp: string[]
}

export interface AuditRequest {
  summary: string
  payload: Record<string, unknown>
}

export interface AuditResponse {
  raw: string
  delivered: string
}

export interface AuditTokens {
  prompt: number
  completion: number
  total: number
}

export interface AuditLatencyStages {
  identity: number
  authorization: number
  dlp: number
  policy: number
  behavior: number
  resource: number
  audit: number
}

export interface AuditLatency {
  proxy_ms: number
  upstream_ms: number
  overhead_ms?: number | null
  stages: AuditLatencyStages
}

export interface AuditDetail {
  call_id: string
  timestamp: string
  identity: AuditIdentity
  kind: CallKind
  target: string
  mcp_server: string | null
  decision: AuditDecision
  matched_rule_yaml: string | null
  request: AuditRequest
  response: AuditResponse
  items_masked: number
  items_restored?: number
  tokens: AuditTokens
  cost_usd: number
  latency: AuditLatency
  overhead_ms?: number | null
  provider: { name: string; model: string }
}
