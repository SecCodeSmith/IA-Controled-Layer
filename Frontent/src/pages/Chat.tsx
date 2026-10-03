import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useMe } from '../api/me'
import { useSendAgentMessage, useResolveAgentApproval } from '../api/agent'
import { getOrCreateTabSessionId } from '../lib/session'
import { errorMessage } from '../lib/errorMessage'
import { ChatHeader } from '../components/layout/ChatHeader'
import { ToolsSidebar } from '../components/chat/ToolsSidebar'
import { PolicySidebar } from '../components/chat/PolicySidebar'
import { ProviderBadge } from '../components/chat/ProviderBadge'
import { UserBubble } from '../components/chat/UserBubble'
import { AgentTurn } from '../components/chat/AgentTurn'
import { ChatInput } from '../components/chat/ChatInput'
import { Spinner } from '../components/common/Spinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import type { ApprovalResolution } from '../components/chat/ApprovalCard'
import type { AgentEvent } from '../types/chat'

type ConversationTurn =
  | { kind: 'user'; id: string; text: string }
  | { kind: 'agent'; id: string; events: AgentEvent[] }

export function Chat() {
  const auth = useAuth()
  const navigate = useNavigate()
  const me = useMe(Boolean(auth.token))
  const sendMessage = useSendAgentMessage()
  const resolveApproval = useResolveAgentApproval()

  const [sessionId] = useState(() => getOrCreateTabSessionId())
  const [turns, setTurns] = useState<ConversationTurn[]>([])
  const [resolvingApprovalId, setResolvingApprovalId] = useState<string | null>(null)
  const [approvalResolutions, setApprovalResolutions] = useState<Record<string, ApprovalResolution>>(
    {},
  )

  useEffect(() => {
    if (!auth.token || !auth.identity) {
      navigate('/')
    }
  }, [auth.token, auth.identity, navigate])

  if (!auth.identity) {
    return null
  }

  async function handleSend(message: string) {
    setTurns((prev) => [...prev, { kind: 'user', id: `u-${Date.now()}`, text: message }])
    const response = await sendMessage.mutateAsync({ sessionId, message })
    setTurns((prev) => [...prev, { kind: 'agent', id: `a-${Date.now()}`, events: response.events }])
  }

  async function handleApprove(approvalId: string) {
    setResolvingApprovalId(approvalId)
    try {
      const response = await resolveApproval.mutateAsync({ sessionId, approvalId, decision: 'approve' })
      setApprovalResolutions((prev) => ({ ...prev, [approvalId]: 'approved' }))
      setTurns((prev) => [...prev, { kind: 'agent', id: `a-${Date.now()}`, events: response.events }])
    } finally {
      setResolvingApprovalId(null)
    }
  }

  async function handleReject(approvalId: string) {
    setResolvingApprovalId(approvalId)
    try {
      const response = await resolveApproval.mutateAsync({ sessionId, approvalId, decision: 'reject' })
      setApprovalResolutions((prev) => ({ ...prev, [approvalId]: 'rejected' }))
      setTurns((prev) => [...prev, { kind: 'agent', id: `a-${Date.now()}`, events: response.events }])
    } finally {
      setResolvingApprovalId(null)
    }
  }

  function handleSignOut() {
    auth.signOut()
    navigate('/')
  }

  return (
    <div className="flex min-h-screen flex-col">
      <ChatHeader
        identity={auth.identity}
        tokensUsed={me.data?.budget.tokens_used ?? 0}
        tokensLimit={me.data?.budget.tokens_limit ?? 0}
        protectionMode={me.data?.protection?.mode}
        onSignOut={handleSignOut}
      />

      <div className="mx-auto flex w-full max-w-[1440px] flex-wrap items-start gap-6 px-8 py-6">
        <aside className="flex max-w-[340px] flex-1 basis-[260px] flex-col gap-4">
          {me.data ? (
            <>
              <ToolsSidebar tools={me.data.tools} role={me.data.identity.role} region={me.data.identity.region} />
              <PolicySidebar name={me.data.policy.name} version={me.data.policy.version} />
              <ProviderBadge provider={me.data.provider} />
            </>
          ) : (
            <Spinner label="Loading your tools…" />
          )}
        </aside>

        <main className="flex min-w-0 flex-[999_1_560px] flex-col rounded-[10px] border border-border bg-white">
          <div className="flex flex-col gap-6 p-7">
            {me.isError ? <ErrorBanner message={errorMessage(me.error)} /> : null}
            {turns.map((turn) =>
              turn.kind === 'user' ? (
                <UserBubble key={turn.id} text={turn.text} />
              ) : (
                <AgentTurn
                  key={turn.id}
                  events={turn.events}
                  resolvingApprovalId={resolvingApprovalId}
                  approvalResolutions={approvalResolutions}
                  onApprove={handleApprove}
                  onReject={handleReject}
                />
              ),
            )}
            {sendMessage.isPending ? <Spinner label="Agent is working…" /> : null}
            {sendMessage.isError ? <ErrorBanner message={errorMessage(sendMessage.error)} /> : null}
          </div>

          <ChatInput onSend={(message) => void handleSend(message)} disabled={sendMessage.isPending} />
        </main>
      </div>
    </div>
  )
}
