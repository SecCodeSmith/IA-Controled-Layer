import { StatusBadge } from '../common/StatusBadge'
import { StageChip } from '../common/StageChip'
import { formatToolCall } from '../../lib/formatToolCall'
import type { ToolCallEvent } from '../../types/chat'

export function ToolCallCard({ event }: { event: ToolCallEvent }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <span className="font-mono text-[13px]">{formatToolCall(event.tool, event.arguments)}</span>
        <StatusBadge status={event.status} />
      </div>
      {event.reason ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-muted">
            {event.reason}
            {event.rule_id ? ` · rule ${event.rule_id}` : ''}
          </span>
          {event.stage ? <StageChip stage={event.stage} /> : null}
        </div>
      ) : null}
      {event.result_preview ? (
        <div className="rounded-md bg-page px-3 py-2.5 font-mono text-xs leading-relaxed text-ink">
          {event.result_preview.split('\n').map((line, index) => (
            <div key={index}>{line}</div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
