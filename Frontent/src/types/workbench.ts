import type { CallStatus, PipelineStage, RuleAction } from './common'

export type TraceKind = 'prompt' | 'tool_call'
export type TracePoint = 'prompt' | 'tool_call' | 'tool_result'
export type ClassifierBand = 'block' | 'escalate' | 'allow'
export type JudgeVerdict = 'allow' | 'flag' | 'block'

export interface TraceToolCall {
  server: string
  tool: string
  arguments: Record<string, unknown>
}

export interface TraceRequest {
  actor: string
  kind: TraceKind
  text?: string
  tool_call?: TraceToolCall
  force_verify?: boolean
}

export interface TraceViolation {
  rule_id: string
  action: RuleAction
  confidence: number
  reason: string | null
  evidence: string[]
}

export interface TraceStage {
  point: TracePoint
  stage: PipelineStage
  action: RuleAction
  timing_ms: number
  cache_hit: boolean
  violations: TraceViolation[]
}

export interface PathStep {
  feature: string
  value: number
  threshold: number
  direction: '<=' | '>'
}

export interface LeafInfo {
  node_id: number
  samples: number
  positive_fraction: number
}

export interface ClassifierExplanation {
  probability: number
  model_type: string
  path: PathStep[]
  leaf: LeafInfo | null
  top_features: string[]
}

export interface ClassifierTrace {
  rule_id: string
  probability: number
  band: ClassifierBand
  sampled: boolean
  forced: boolean
  explanation: ClassifierExplanation | null
}

export interface JudgeTrace {
  verdict: JudgeVerdict
  confidence: number
  reason: string | null
}

export interface TraceResponse {
  call_id: string
  kind: TraceKind
  status: CallStatus
  action: RuleAction
  stage: PipelineStage | null
  rule_id: string | null
  reason: string | null
  masked_text: string | null
  stages: TraceStage[]
  classifier_trace: ClassifierTrace | null
  judge: JudgeTrace | null
  training_sample_id: string | null
  raw_result: unknown
  delivered_result: unknown
}

export interface ResourceGrantView {
  paths: { allow: string[]; deny: string[] }
  columns: { allow: string[] | null; deny: string[] }
  rows: Record<string, string | string[]>
}

export interface ResourceView {
  id: string
  server: string
  tools: string[]
  path_argument: string | null
  records: string | null
  grants: Record<string, ResourceGrantView>
}

export interface ResourceMatrixResponse {
  roles: string[]
  resources: ResourceView[]
}
