import { ToolCallCard } from './ToolCallCard'
import { ApprovalCard, type ApprovalResolution } from './ApprovalCard'
import type { AgentEvent } from '../../types/chat'

interface AgentTurnProps {
  events: AgentEvent[]
  resolvingApprovalId: string | null
  approvalResolutions: Record<string, ApprovalResolution>
  onApprove: (approvalId: string) => void
  onReject: (approvalId: string) => void
}

export function AgentTurn({
  events,
  resolvingApprovalId,
  approvalResolutions,
  onApprove,
  onReject,
}: AgentTurnProps) {
  return (
    <div className="flex max-w-[85%] flex-col gap-2.5">
      <span className="text-[13px] font-semibold text-muted">Agent</span>
      {events.map((event, index) => {
        if (event.type === 'tool_call') {
          return <ToolCallCard key={event.call_id} event={event} />
        }
        if (event.type === 'approval_required') {
          return (
            <ApprovalCard
              key={event.approval_id}
              event={event}
              pending={resolvingApprovalId === event.approval_id}
              resolution={approvalResolutions[event.approval_id] ?? null}
              onApprove={() => onApprove(event.approval_id)}
              onReject={() => onReject(event.approval_id)}
            />
          )
        }
        return (
          <p key={`text-${index}`} className="mt-1 text-[15px] leading-relaxed">
            {event.text}
          </p>
        )
      })}
    </div>
  )
}
