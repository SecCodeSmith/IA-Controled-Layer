import { useMutation, useQueryClient } from '@tanstack/react-query'
import { agentApi } from './client'
import type { AgentChatResponse, ApprovalDecision } from '../types/chat'

interface SendMessageInput {
  sessionId: string
  message: string
}

export function useSendAgentMessage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, message }: SendMessageInput) =>
      agentApi.post<AgentChatResponse>(
        '/agent/chat',
        { session_id: sessionId, message },
        { sessionId },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

interface ResolveApprovalInput {
  sessionId: string
  approvalId: string
  decision: ApprovalDecision
}

export function useResolveAgentApproval() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, approvalId, decision }: ResolveApprovalInput) =>
      agentApi.post<AgentChatResponse>(
        `/agent/approvals/${approvalId}`,
        { session_id: sessionId, decision },
        { sessionId },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

interface ResetSessionResponse {
  session_id: string
  cleared: boolean
}

export function useResetChatSession() {
  return useMutation({
    mutationFn: (sessionId: string) =>
      agentApi.post<ResetSessionResponse>(
        `/agent/sessions/${encodeURIComponent(sessionId)}/reset`,
        {},
        { sessionId },
      ),
  })
}
