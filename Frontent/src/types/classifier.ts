export type SampleLabel = 0 | 1
import type { InterceptionPoint } from './common'

export type SampleSource = 'judge' | 'workbench' | 'curation' | 'manual'
export type SampleStatus = 'pending' | 'accepted' | 'rejected'
export type RetrainJobStatus = 'running' | 'complete' | 'failed'

export interface ClassifierInfo {
  loaded: boolean
  path: string | null
  model_type: string | null
  version: number
  trained_at: string | null
  f1: number | null
  n_base: number
  n_feedback: number
}

export interface SampleCounts {
  pending: number
  accepted: number
  rejected: number
  total: number
}

export interface TrainingSample {
  id: string
  text: string
  text_sha256: string
  label: SampleLabel
  source: SampleSource
  status: SampleStatus
  confidence: number | null
  reason: string | null
  tree_probability: number | null
  point: InterceptionPoint | null
  call_id: string | null
  created_at: string
  reviewed_by: string | null
}

export interface RetrainResult {
  f1: number
  passed_gate: boolean
  swapped: boolean
  n_base: number
  n_feedback: number
  version: number
  trained_at: string
}

export interface ClassifierStatusResponse {
  tree: ClassifierInfo
  counts: SampleCounts
  retrain_running: boolean
  last_retrain: RetrainResult | null
}

export interface SampleListResponse {
  items: TrainingSample[]
}

export interface SamplePatch {
  label?: SampleLabel
  status?: SampleStatus
}

export interface CurateRequest {
  limit?: number
}

export interface CurationSummary {
  reviewed: number
  accepted: number
  rejected: number
  relabelled: number
  refused: number
  error: string | null
}

export interface RetrainRequest {
  include_pending?: boolean
  seed?: number
}

export interface RetrainJobResponse {
  job_id: string
  status: RetrainJobStatus
  started_at: string
  finished_at: string | null
  result: RetrainResult | null
  error: string | null
}

export interface RetrainProgressEvent {
  step: string
}

export interface RetrainFailedEvent {
  error: string
}
