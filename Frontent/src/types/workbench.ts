import type { CallStatus, PipelineStage } from './common'

export type TraceKind = 'prompt' | 'tool_call'
export type ClassifierBand = 'block' | 'inconclusive' | 'allow'

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
  action: string
  confidence: number
  reason: string | null
  evidence: string[]
}

export interface TraceStage {
  stage: PipelineStage
  action: string
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
  explanation: ClassifierExplanation
}

export interface JudgeTrace {
  verdict: string
  confidence: number
  reason: string | null
}

export interface TraceResponse {
  call_id: string
  kind: string
  status: CallStatus
  action: string
  stage: PipelineStage | null
  rule_id: string | null
  reason: string | null
  masked_text: string | null
  stages: TraceStage[]
  classifier_trace: ClassifierTrace | null
  judge: JudgeTrace | null
  training_sample_id: string | null
  raw_result: string | null
  delivered_result: string | null
}

export interface ResourceGrantView {
  paths: { allow: string[]; deny: string[] } | null
  columns: { allow: string[] | null; deny: string[] } | null
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
