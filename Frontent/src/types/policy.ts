import type { InterceptionPoint, PipelineStage, RuleAction } from './common'

export interface PolicyRule {
  id: string
  type?: string
  stage?: PipelineStage
  on?: InterceptionPoint | InterceptionPoint[]
  match?: Record<string, unknown>
  detect?: string[]
  action: RuleAction
  params?: Record<string, unknown>
  owasp?: string[]
  severity?: string
  enabled?: boolean
  overridden?: boolean
}

export type RulesByStage = Partial<Record<PipelineStage, PolicyRule[]>>

export interface PolicyDocumentView {
  version: number
  profile?: string
  [key: string]: unknown
}

export interface PolicyResponse {
  version: number
  status: 'LOADED' | 'ERROR'
  loaded_at: string
  source: string
  error: string | null
  raw_yaml: string
  document: PolicyDocumentView
  rules_by_stage: RulesByStage
}
