import type { CallStatus, PipelineStage } from './common'

export interface FeedUser {
  sub: string
  name: string
  role: string
}

export type CallKind = 'tool_call' | 'chat'

export interface FeedRow {
  call_id: string
  time: string
  user: FeedUser
  kind: CallKind
  target: string
  status: CallStatus
  stage: PipelineStage | null
  rule_id: string | null
  reason: string
}

export interface FeedListResponse {
  items: FeedRow[]
}

export interface Alert {
  id: string
  created_at: string
  call_id: string
  user: FeedUser
  status: CallStatus
  stage: PipelineStage | null
  rule_id: string | null
  severity: string
  owasp: string[]
  reason: string
  evidence: string | null
}

export interface AlertListResponse {
  items: Alert[]
}

export interface BudgetUsageRow {
  sub: string
  name: string
  tokens_used: number
  tokens_limit: number
  cost_used_usd: number
}

export interface RiskRow {
  sub: string
  name: string
  score: number
  level: string
}

export interface LatencyStats {
  proxy_p50_ms: number
  proxy_p95_ms: number
  upstream_p50_ms: number
  upstream_p95_ms: number
}

export interface StatsResponse {
  total_calls: number
  allowed: number
  blocked: number
  masked: number
  escalated: number
  flagged: number
  by_stage: Record<string, number>
  by_rule: Record<string, number>
  by_owasp: Record<string, number>
  by_role: Record<string, number>
  budget: { users: BudgetUsageRow[] }
  risk: RiskRow[]
  posture_score: number
  cache_hit_ratio: number
  latency: LatencyStats
  provider: { name: string; model: string }
  policy: { version: number; status: 'LOADED' | 'ERROR' }
}
