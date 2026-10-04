import type { PipelineStage, ScenarioStatus } from './common'
import type { ProtectionMode } from './protection'

export type ScenarioVia = 'agent' | 'scripted' | null

export type ScenarioKind = 'negative' | 'positive'

export interface ScenarioExpected {
  status: string
  rule_id?: string | null
}

export interface ScenarioObserved {
  status: string
  stage?: PipelineStage | null
  rule_id?: string | null
  reason?: string | null
  target?: string | null
  call_id?: string | null
  http_status?: number | null
}

export interface ScenarioStep {
  action: string
  server?: string
  tool?: string
  arguments?: Record<string, unknown>
  message?: string
  model?: string
  max_tokens?: number
  times?: number
  vary?: string
  step?: string
  claim?: string
  value?: unknown
}

export interface TraceEntry {
  target: string
  status: string
  stage: PipelineStage | null
  rule_id: string | null
  reason: string | null
  call_id: string | null
  http_status: number | null
}

export interface Scenario {
  id: string
  name: string
  kind: ScenarioKind
  actor: string
  stage: PipelineStage
  expected: ScenarioExpected
  owasp: string[]
  description?: string
  prompt?: string
  steps?: ScenarioStep[]
  trace?: TraceEntry[]
  explanation?: string | null
  error?: string | null
  agent_driven?: boolean
  via?: ScenarioVia
  status?: ScenarioStatus
  observed?: ScenarioObserved | null
  duration_ms?: number | null
}

export interface ScenariosResponse {
  scenarios: Scenario[]
}

export type AttackAgentMode = 'scripted' | 'ollama'

export interface AttackRunSummary {
  stopped: number
  passed: number
  succeeded: number
  not_attempted: number
  error: number
  running: number
  pending: number
}

export interface AttackRun {
  run_id: string
  number: number
  agent: AttackAgentMode
  provider: string
  model: string
  protection_mode: ProtectionMode
  started_at: string
  scenarios: Scenario[]
  summary?: AttackRunSummary
}

export interface AttackScenarioStreamEvent {
  id: string
  status: ScenarioStatus
  observed: ScenarioObserved | null
  duration_ms: number | null
  via?: ScenarioVia
  trace?: TraceEntry[]
  explanation?: string | null
  error?: string | null
}

export interface AttackRunCompleteEvent {
  summary: AttackRunSummary
}
