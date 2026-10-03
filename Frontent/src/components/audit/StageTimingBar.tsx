import { formatMs } from '../../lib/formatMs'
import { PIPELINE_STAGE_ORDER } from '../../types/common'
import type { AuditLatencyStages } from '../../types/audit'

const STAGE_COLORS = ['#2348B8', '#17613F', '#7A4E00', '#A3301A', '#8FB3FF', '#5A5F66', '#16181B']

export function StageTimingBar({ stages }: { stages: AuditLatencyStages }) {
  const total = PIPELINE_STAGE_ORDER.reduce((sum, stage) => sum + stages[stage], 0)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-3 overflow-hidden rounded-full bg-border-soft" role="img" aria-label="Per-stage timing">
        {PIPELINE_STAGE_ORDER.map((stage, index) => {
          const share = total > 0 ? (stages[stage] / total) * 100 : 0
          return (
            <div
              key={stage}
              style={{ width: `${Math.max(share, stages[stage] > 0 ? 2 : 0)}%`, background: STAGE_COLORS[index] }}
              title={`${stage}: ${formatMs(stages[stage])}`}
            />
          )
        })}
      </div>
      <div className="flex flex-wrap gap-3 font-mono text-xs text-muted">
        {PIPELINE_STAGE_ORDER.map((stage, index) => (
          <span key={stage} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: STAGE_COLORS[index] }} />
            {stage} · {formatMs(stages[stage])}
          </span>
        ))}
      </div>
    </div>
  )
}
