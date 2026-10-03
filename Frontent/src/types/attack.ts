import type { PipelineStage, ScenarioStatus } from './common'

export type ScenarioKind = 'negative' | 'positive'

export interface ScenarioExpected {
  status: string
  rule_id?: string | null
}

export interface ScenarioObserved {
  status: string
  stage?: PipelineStage | null
  rule_id?: string | null
}

export interface Scenario {
  id: string
  name: string
  kind: ScenarioKind
  actor: string
  stage: PipelineStage
  expected: ScenarioExpected
  owasp: string[]
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
  running: number
  pending: number
}

export interface AttackRun {
  run_id: string
  number: number
  agent: AttackAgentMode
  started_at: string
  scenarios: Scenario[]
  summary?: AttackRunSummary
}

export interface AttackScenarioStreamEvent {
  id: string
  status: ScenarioStatus
  observed: ScenarioObserved | null
  duration_ms: number | null
}

export interface AttackRunCompleteEvent {
  summary: AttackRunSummary
}
