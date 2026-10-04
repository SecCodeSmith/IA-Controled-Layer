import { StatusBadge } from '../common/StatusBadge'
import type { TraceResponse } from '../../types/workbench'

function decisionLabel(trace: TraceResponse): string {
  const label = [trace.stage, trace.rule_id].filter(Boolean).join(' · ')
  return label || 'no rule matched'
}

export function TraceVerdict({ trace }: { trace: TraceResponse }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <StatusBadge status={trace.status} />
      <span className="font-mono text-[13px]">{decisionLabel(trace)}</span>
      {trace.reason ? <span className="text-[13px] text-muted">{trace.reason}</span> : null}
    </div>
  )
}
