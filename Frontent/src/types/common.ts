export type CallStatus = 'ALLOWED' | 'MASKED' | 'BLOCKED' | 'ESCALATED' | 'FLAGGED'

export type PipelineStage =
  | 'identity'
  | 'authorization'
  | 'dlp'
  | 'policy'
  | 'behavior'
  | 'resource'
  | 'audit'

export const PIPELINE_STAGE_ORDER: readonly PipelineStage[] = [
  'identity',
  'authorization',
  'dlp',
  'policy',
  'behavior',
  'resource',
  'audit',
]

export type InterceptionPoint = 'prompt' | 'response' | 'tool_call' | 'tool_result'

export type RuleAction = 'allow' | 'flag' | 'mask' | 'block' | 'require_approval' | 'quarantine'

export type UserRole = 'developer' | 'hr' | 'finance'

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'executed' | 'expired'

export type ScenarioStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'STOPPED'
  | 'PASSED'
  | 'SUCCEEDED'
  | 'NOT_ATTEMPTED'
  | 'ERROR'

export type ProviderName = 'ollama' | 'mock' | 'openai_compatible'

export interface ProviderInfo {
  name: ProviderName
  model: string
}

export interface ErrorEnvelope {
  error: {
    code: string
    status?: CallStatus
    stage?: PipelineStage | null
    rule_id?: string | null
    reason: string
    owasp?: string[]
    call_id?: string | null
  }
}

export class ApiError extends Error {
  readonly envelope: ErrorEnvelope
  readonly httpStatus: number

  constructor(envelope: ErrorEnvelope, httpStatus: number) {
    super(envelope.error.reason)
    this.envelope = envelope
    this.httpStatus = httpStatus
  }
}
