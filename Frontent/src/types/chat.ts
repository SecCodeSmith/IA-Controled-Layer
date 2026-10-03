import type { CallStatus, PipelineStage } from './common'

export type AgentEventType = 'tool_call' | 'approval_required' | 'assistant_text'

export interface ToolCallEvent {
  type: 'tool_call'
  call_id: string
  tool: string
  arguments: Record<string, unknown>
  status: CallStatus
  stage: PipelineStage | null
  rule_id: string | null
  reason: string
  items_masked: number
  result_preview: string | null
}

export interface ApprovalRequiredEvent {
  type: 'approval_required'
  approval_id: string
  tool: string
  arguments: Record<string, unknown>
  rule_id: string
  reason: string
}

export interface AssistantTextEvent {
  type: 'assistant_text'
  text: string
}

export type AgentEvent = ToolCallEvent | ApprovalRequiredEvent | AssistantTextEvent

export interface AgentBudgetSummary {
  tokens_used: number
  tokens_limit: number
}

export interface AgentChatResponse {
  session_id: string
  events: AgentEvent[]
  budget: AgentBudgetSummary
}

export interface AgentChatRequest {
  session_id: string
  message: string
}

export type ApprovalDecision = 'approve' | 'reject'

export interface AgentApprovalRequest {
  session_id: string
  decision: ApprovalDecision
}

export interface AgentHealthResponse {
  status: string
  control_layer: string
  provider: {
    name: string
    model: string
  }
}
