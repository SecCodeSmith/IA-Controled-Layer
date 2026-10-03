import { ShieldLogo } from '../common/ShieldLogo'
import { StatusBadge } from '../common/StatusBadge'
import { formatToolCall } from '../../lib/formatToolCall'
import type { ApprovalRequiredEvent } from '../../types/chat'

export type ApprovalResolution = 'approved' | 'rejected'

interface ApprovalCardProps {
  event: ApprovalRequiredEvent
  pending: boolean
  resolution: ApprovalResolution | null
  onApprove: () => void
  onReject: () => void
}

export function ApprovalCard({ event, pending, resolution, onApprove, onReject }: ApprovalCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-[10px] border-[1.5px] border-accent bg-accent-soft p-[18px]">
      <div className="flex items-center gap-2.5">
        <ShieldLogo size={20} color="#2348B8" />
        <span className="text-[15px] font-semibold">Approval required</span>
      </div>
      <span className="font-mono text-[13px]">{formatToolCall(event.tool, event.arguments)}</span>
      <span className="text-[13px] text-muted">
        {event.reason} · rule {event.rule_id}
      </span>
      {resolution ? (
        <StatusBadge status={resolution === 'approved' ? 'ALLOWED' : 'BLOCKED'} />
      ) : (
        <div className="flex flex-wrap gap-2.5">
          <button
            type="button"
            onClick={onReject}
            disabled={pending}
            className="min-h-11 rounded-lg border border-border bg-white px-5 text-sm font-medium text-ink disabled:opacity-50"
          >
            Reject
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={pending}
            className="min-h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Approve
          </button>
        </div>
      )}
    </div>
  )
}
